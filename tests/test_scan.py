import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import anthropic
import pytest
from test_parallel import SMALL_PUZZLES

from last_piece_puzzle import scan, solver
from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Bit, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.scan import SheetKind, SolvedBoard
from last_piece_puzzle.solution import load_solution

ROOT = Path(__file__).parent.parent
GRIDS = [
    load_solution(Path(__file__).parent / "fixtures" / f"golfing_madness_solution_{n}.txt").grid
    for n in range(1, 6)
]
FLIP = {Tab.IN: Tab.OUT, Tab.OUT: Tab.IN}


def solved_board(grid: Sequence[str] = GRIDS[0]) -> SolvedBoard:
    """The board of a fixture solution as a solved sheet would describe it."""
    board = Board.from_grid(PUZZLE, grid)
    assert board is not None
    cells: list[tuple[tuple[str, scan.Tabs], ...]] = []
    for r in range(board.rows):
        row: list[tuple[str, scan.Tabs]] = []
        for c in range(board.cols):
            cell = board.cell(r, c)
            assert cell is not None
            row.append((cell[0], scan.bit_tabs(cell[1])))
        cells.append(tuple(row))
    names = {piece.letter: piece.name for piece in PUZZLE.pieces}
    return SolvedBoard(PUZZLE.name, names, tuple(cells), PUZZLE.border)


def with_tab(board: SolvedBoard, row: int, col: int, side: int, tab: Tab) -> SolvedBoard:
    """The board with one side of one cell changed."""
    cells = [list(line) for line in board.cells]
    letter, tabs = cells[row][col]
    new = list(tabs)
    new[side] = tab
    cells[row][col] = (letter, (new[0], new[1], new[2], new[3]))
    return dataclasses.replace(board, cells=tuple(tuple(line) for line in cells))


def without_border(text: str) -> str:
    return "".join(
        line
        for line in text.splitlines(keepends=True)
        if line.split(":")[0] not in scan.BORDER_SIDES
    )


def canonical(piece: Piece) -> frozenset[frozenset[tuple[int, int, Tab, Tab, Tab, Tab]]]:
    """A piece's four rotations, each moved to the origin: the same for every rotation of it."""
    shapes: list[frozenset[tuple[int, int, Tab, Tab, Tab, Tab]]] = []
    for k in range(4):
        rotation = piece.placements[k * len(piece.bits)]
        top, left = min((b.row, b.col) for b in rotation)
        shapes.append(frozenset((b.row - top, b.col - left, *scan.bit_tabs(b)) for b in rotation))
    return frozenset(shapes)


def grids(puzzle: Puzzle) -> set[tuple[str, ...]]:
    return {found.solution.grid for found in solver.solve(puzzle, method="dlx").solutions}


@pytest.mark.spec("SPEC-0011", "AT-0001")
@pytest.mark.parametrize("border", [True, False])
def test_solved_sheet_gives_golfing_madness(border: bool) -> None:
    text = scan.format_solved_sheet(solved_board())
    board = scan.parse_solved_sheet(text if border else without_border(text))
    assert board == solved_board()
    assert board.grid.grid == GRIDS[0]
    puzzle = board.to_puzzle()
    assert [p.letter for p in puzzle.pieces] == [p.letter for p in PUZZLE.pieces]
    for piece, expected in zip(puzzle.pieces, PUZZLE.pieces, strict=True):
        assert piece.name == expected.name
        assert canonical(piece) == canonical(expected)
    assert puzzle.border == PUZZLE.border
    assert grids(puzzle) == set(GRIDS)


def bad_solved_sheets() -> list[tuple[str, str]]:
    board = solved_board()  # rows 0 and 1: E E E H J J J J / E H H H G N N J
    text = scan.format_solved_sheet(board)
    lines = text.splitlines(keepends=True)
    row_line = next(n for n, line in enumerate(lines) if line.startswith("row:"))
    short_row = lines.copy()
    short_row[row_line + 1] = short_row[row_line + 1].rsplit(" ", 1)[0] + "\n"
    short_tabs = text.replace("row: E:", "row: E:II ", 1)
    no_piece_line = "".join(line for line in lines if not line.startswith("piece N:"))
    top = "".join("O" if t is Tab.OUT else "I" for t in PUZZLE.border.top)
    same_as_cell = "I" if board.cells[0][0][1][0] is Tab.IN else "O"
    east_of_e = board.cells[0][2][1][3]
    return [
        (text.replace("name:", "nonsense\nname:"), "line 2: cannot read 'nonsense'"),
        ("".join(short_row), f"line {row_line + 2}: row has 7 cells, the first row has 8"),
        (short_tabs, f"line {row_line + 1}, cell E:II: 'II' has 2 tabs, expected 4"),
        (
            text.replace("row: E:OO--", "row: E:OX--", 1),
            f"line {row_line + 1}, cell E:OX--: tab 'X' is not I, O or -",
        ),
        (no_piece_line, "cell (1, 5): piece N has no piece line"),
        (
            scan.format_solved_sheet(with_tab(board, 0, 2, 3, Tab.NONE)),
            "cell (0, 2) E east: - faces piece H",
        ),
        (
            scan.format_solved_sheet(with_tab(board, 0, 0, 3, Tab.OUT)),
            "cell (0, 0) E east: O faces its own piece",
        ),
        (
            scan.format_solved_sheet(with_tab(board, 0, 0, 0, Tab.NONE)),
            "cell (0, 0) E north: - faces the frame",
        ),
        (
            scan.format_solved_sheet(with_tab(board, 0, 2, 3, FLIP[east_of_e])),
            f"cell (0, 2) E east is {scan.TAB_CHARS[FLIP[east_of_e]]} and cell (0, 3) H west",
        ),
        (
            text.replace(f"top:    {top}", f"top:    {same_as_cell}{top[1:]}"),
            "top tab 0 is",
        ),
    ]


@pytest.mark.spec("SPEC-0011", "AT-0002")
@pytest.mark.parametrize(
    ("text", "message"), [pytest.param(*case, id=case[1]) for case in bad_solved_sheets()]
)
def test_bad_solved_sheet_names_the_fault(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}"):
        scan.parse_solved_sheet(text)


@pytest.mark.spec("SPEC-0011", "AT-0002")
def test_one_flipped_inside_tab_is_found_at_its_pair_of_cells() -> None:
    board = solved_board()
    for r, row in enumerate(board.cells):
        for c, (_, tabs) in enumerate(row):
            for k, tab in enumerate(tabs):
                if tab is Tab.NONE:
                    continue
                dr, dc = scan.CELL_SIDES[k][1:]
                nr, nc = r + dr, c + dc
                if not (0 <= nr < 8 and 0 <= nc < 8):
                    continue
                text = scan.format_solved_sheet(with_tab(board, r, c, k, FLIP[tab]))
                with pytest.raises(ValueError, match="touching tabs must differ") as error:
                    scan.parse_solved_sheet(text)
                message = str(error.value)
                assert f"({r}, {c})" in message and f"({nr}, {nc})" in message


@pytest.mark.spec("SPEC-0011", "AT-0003")
@pytest.mark.parametrize("puzzle", [PUZZLE, *SMALL_PUZZLES.values()], ids=lambda p: p.name)
def test_piece_sheet_round_trips(puzzle: Puzzle) -> None:
    assert scan.parse_piece_sheet(scan.format_piece_sheet(puzzle)) == puzzle


@pytest.mark.spec("SPEC-0011", "AT-0003")
@pytest.mark.parametrize(
    ("change", "message"),
    [
        (("name: Golfing Madness", "name: Golfing Madness\n  0,0 III-"), "line 3: a cell before"),
        (("piece A: Bluehat", "colour: green\npiece A: Bluehat"), "line 9: unknown key 'colour'"),
        (("piece A: Bluehat", "Bluehat"), "line 9: cannot read 'Bluehat'"),
        (("  0,0 III-", "  0,0 IIX-"), "line 10: tab 'X' is not I, O or -"),
        (("  0,0 III-", "  0,0 III"), "line 10: 'III' has 3 tabs, expected 4"),
        (("top:    ", "top:    IO\ntop:    "), "line 5: top given twice"),
        (("bottom: OIOIOIII", ""), "no bottom line"),
    ],
)
def test_bad_piece_sheet(change: tuple[str, str], message: str) -> None:
    text = scan.format_piece_sheet(PUZZLE).replace(*change, 1)
    with pytest.raises(ValueError, match=f"^{re.escape(message)}"):
        scan.parse_piece_sheet(text)


def flipped_piece_tabs() -> list[Puzzle]:
    puzzles: list[Puzzle] = []
    for i, piece in enumerate(PUZZLE.pieces):
        for j, bit in enumerate(piece.bits):
            for k, tab in enumerate(scan.bit_tabs(bit)):
                if tab is Tab.NONE:
                    continue
                tabs = list(scan.bit_tabs(bit))
                tabs[k] = FLIP[tab]
                bits = list(piece.bits)
                bits[j] = Bit(bit.row, bit.col, *tabs)
                pieces = list(PUZZLE.pieces)
                pieces[i] = dataclasses.replace(piece, bits=tuple(bits))
                puzzles.append(dataclasses.replace(PUZZLE, pieces=tuple(pieces)))
    return puzzles


def flipped_border_tabs() -> list[Puzzle]:
    puzzles: list[Puzzle] = []
    for side in scan.BORDER_SIDES:
        tabs = getattr(PUZZLE.border, side)
        for k, tab in enumerate(tabs):
            new = (*tabs[:k], FLIP[tab], *tabs[k + 1 :])
            border = dataclasses.replace(PUZZLE.border, **{side: new})
            puzzles.append(dataclasses.replace(PUZZLE, border=border))
    return puzzles


@pytest.mark.spec("SPEC-0011", "AT-0004")
def test_tab_balance() -> None:
    assert scan.tab_balance(PUZZLE) == 0
    pieces, border = flipped_piece_tabs(), flipped_border_tabs()
    assert len(pieces) > 100 and len(border) == 32
    assert all(scan.tab_balance(puzzle) in (-2, 2) for puzzle in pieces + border)


class FakeModel:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[list[Path], SheetKind]] = []

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        self.calls.append((list(photos), kind))
        return self.text


class NoModel:
    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        raise AssertionError("the model must not be called")


def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workdir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "puzzles").mkdir()
    return tmp_path


def run(argv: list[str], model: scan.VisionModel, workdir: Path) -> None:
    scan.main(argv, model=model, puzzles_dir=workdir / "puzzles")


@pytest.mark.spec("SPEC-0011", "AT-0005")
def test_scan_writes_sheets_and_module(workdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    model = FakeModel(scan.format_solved_sheet(solved_board()))
    run(["test_key", "photo.jpg"], model, workdir)
    assert model.calls == [([Path("photo.jpg")], SheetKind.SOLVED)]
    folder = workdir / "scans" / "test_key"
    assert (folder / "sheet.txt").read_text() == model.text
    module = workdir / "puzzles" / "test_key_puzzle.py"
    puzzle = load_module(module).PUZZLE
    assert scan.parse_piece_sheet((folder / "pieces.txt").read_text()) == puzzle
    assert grids(puzzle) == set(GRIDS)
    assert "5 solutions found." in capsys.readouterr().out

    # The module is not replaced without --force, and the sheet (maybe fixed by hand) never is.
    with pytest.raises(SystemExit) as stopped:
        run(["test_key", "photo.jpg"], model, workdir)
    assert stopped.value.code == 1
    assert "use --force" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        run(["test_key", "photo.jpg", "--force"], model, workdir)
    assert "may have hand fixes" in capsys.readouterr().err
    module.write_text("")
    run(["test_key", "--sheet", str(folder / "sheet.txt"), "--force"], NoModel(), workdir)
    assert puzzle == load_module(module).PUZZLE
    assert len(model.calls) == 1


@pytest.mark.spec("SPEC-0011", "AT-0005")
def test_pieces_option_asks_for_a_piece_sheet(workdir: Path) -> None:
    model = FakeModel(scan.format_piece_sheet(PUZZLE))
    run(["test_key", "a.jpg", "b.jpg", "--pieces"], model, workdir)
    assert model.calls == [([Path("a.jpg"), Path("b.jpg")], SheetKind.PIECES)]
    assert load_module(workdir / "puzzles" / "test_key_puzzle.py").PUZZLE == PUZZLE


def failing_sheets() -> list[tuple[str, list[str], str]]:
    board = solved_board()
    clash = scan.format_solved_sheet(with_tab(board, 0, 2, 3, FLIP[board.cells[0][2][1][3]]))
    flipped = scan.format_piece_sheet(flipped_piece_tabs()[0])
    # Two flips that cancel out: the tabs balance, but nothing fits.
    a, b = PUZZLE.pieces[0], PUZZLE.pieces[1]  # A's first bit has north I, B's north O
    unsolvable = dataclasses.replace(
        PUZZLE,
        pieces=(
            dataclasses.replace(
                a, bits=(Bit(0, 0, Tab.OUT, Tab.IN, Tab.IN, Tab.NONE), *a.bits[1:])
            ),
            dataclasses.replace(
                b, bits=(Bit(0, 0, Tab.IN, Tab.OUT, Tab.OUT, Tab.NONE), *b.bits[1:])
            ),
            *PUZZLE.pieces[2:],
        ),
    )
    assert scan.tab_balance(unsolvable) == 0
    return [
        (clash, [], "touching tabs must differ"),
        (flipped, ["--pieces"], "tabs don't balance (off by"),
        (scan.format_piece_sheet(unsolvable), ["--pieces"], "the puzzle has no solution"),
    ]


@pytest.mark.spec("SPEC-0011", "AT-0006")
@pytest.mark.parametrize(
    ("text", "options", "message"), [pytest.param(*case, id=case[2]) for case in failing_sheets()]
)
def test_failed_check_writes_no_module(
    workdir: Path, capsys: pytest.CaptureFixture[str], text: str, options: list[str], message: str
) -> None:
    with pytest.raises(SystemExit) as stopped:
        run(["test_key", "photo.jpg", *options], FakeModel(text), workdir)
    assert stopped.value.code == 1
    error = capsys.readouterr().err
    assert message in error
    assert "last-piece-scan test_key --sheet scans/test_key/sheet.txt" in error
    assert (workdir / "scans" / "test_key" / "sheet.txt").read_text() == text
    assert not (workdir / "puzzles" / "test_key_puzzle.py").exists()


@pytest.mark.spec("SPEC-0011", "AT-0007")
def test_sheet_option_skips_the_model(workdir: Path) -> None:
    sheet = workdir / "fixed.txt"
    sheet.write_text(without_border(scan.format_solved_sheet(solved_board())))
    run(["test_key", "--sheet", str(sheet)], NoModel(), workdir)
    assert (workdir / "puzzles" / "test_key_puzzle.py").exists()


@pytest.mark.spec("SPEC-0011", "AT-0007")
@pytest.mark.parametrize(
    "argv", [["test_key"], ["test_key", "a.jpg", "--sheet", "s.txt"], ["Bad-Key", "a.jpg"]]
)
def test_bad_arguments(workdir: Path, argv: list[str]) -> None:
    with pytest.raises(SystemExit) as stopped:
        run(argv, NoModel(), workdir)
    assert stopped.value.code == 2


@pytest.mark.spec("SPEC-0011", "B-0006")
def test_module_loads_and_passes_ruff(tmp_path: Path) -> None:
    path = tmp_path / "golfing_puzzle.py"
    path.write_text(scan.write_module(PUZZLE, "golfing"))
    assert load_module(path).PUZZLE == PUZZLE
    config = str(ROOT / "pyproject.toml")
    for command in (["check"], ["format", "--check"]):
        subprocess.run(
            [sys.executable, "-m", "ruff", *command, "--config", config, str(path)], check=True
        )


@pytest.mark.slow
@pytest.mark.spec("SPEC-0011", "B-0006")
def test_module_passes_mypy(tmp_path: Path) -> None:
    path = tmp_path / "golfing_puzzle.py"
    path.write_text(scan.write_module(PUZZLE, "golfing"))
    env = {**os.environ, "MYPYPATH": str(ROOT / "src")}  # check against the source, not the install
    subprocess.run([sys.executable, "-m", "mypy", "--strict", str(path)], check=True, env=env)


# ClaudeVisionModel, with the SDK client replaced by a stub


class StubClient:
    def __init__(self, stop_reason: str, text: str, category: str | None = None) -> None:
        details = SimpleNamespace(category=category) if category else None
        blocks = [
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ]
        self.message = SimpleNamespace(
            stop_reason=stop_reason, stop_details=details, content=blocks
        )
        self.requests: list[dict[str, object]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self.stream))

    def stream(self, **request: object) -> StubClient:
        self.requests.append(request)
        return self

    def __enter__(self) -> StubClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_final_message(self) -> SimpleNamespace:
        return self.message


def model_with(client: StubClient) -> scan.ClaudeVisionModel:
    return scan.ClaudeVisionModel(cast(anthropic.Anthropic, client))


def solved_json(board: SolvedBoard) -> str:
    chars = scan.TAB_CHARS
    sides = [side for side, _, _ in scan.CELL_SIDES]
    return json.dumps(
        {
            "name": board.name,
            "pieces": [{"letter": k, "name": v} for k, v in board.names.items()],
            "rows": [
                [
                    {"letter": letter, **{s: chars[t] for s, t in zip(sides, tabs, strict=True)}}
                    for letter, tabs in row
                ]
                for row in board.cells
            ],
            "border": {
                side: "".join(chars[t] for t in getattr(board.border, side))
                for side in scan.BORDER_SIDES
            },
        }
    )


def pieces_json(puzzle: Puzzle) -> str:
    chars = scan.TAB_CHARS
    return json.dumps(
        {
            "name": puzzle.name,
            "border": {
                side: "".join(chars[t] for t in getattr(puzzle.border, side))
                for side in scan.BORDER_SIDES
            },
            "pieces": [
                {
                    "letter": piece.letter,
                    "name": piece.name,
                    "cells": [
                        {
                            "row": b.row,
                            "col": b.col,
                            "north": chars[b.north],
                            "west": chars[b.west],
                            "south": chars[b.south],
                            "east": chars[b.east],
                        }
                        for b in piece.bits
                    ],
                }
                for piece in puzzle.pieces
            ],
        }
    )


@pytest.fixture
def photos(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / "solved.JPG", tmp_path / "frame.png"]
    for path in paths:
        path.write_bytes(b"not really an image")
    return paths


@pytest.mark.spec("SPEC-0011", "AT-0008")
def test_claude_request_and_solved_answer(photos: list[Path]) -> None:
    client = StubClient("end_turn", solved_json(solved_board()))
    text = model_with(client).read(photos, SheetKind.SOLVED)
    assert text == scan.format_solved_sheet(solved_board())
    [request] = client.requests
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": scan.SCHEMAS[SheetKind.SOLVED]},
    }
    messages = cast(list[dict[str, list[dict[str, object]]]], request["messages"])
    [message] = messages
    images = [block for block in message["content"] if block["type"] == "image"]
    assert [cast(dict[str, str], block["source"])["media_type"] for block in images] == [
        "image/jpeg",
        "image/png",
    ]
    assert message["content"][-1] == {"type": "text", "text": scan.PROMPTS[SheetKind.SOLVED]}


@pytest.mark.spec("SPEC-0011", "AT-0008")
def test_claude_pieces_answer(photos: list[Path]) -> None:
    client = StubClient("end_turn", pieces_json(PUZZLE))
    text = model_with(client).read(photos, SheetKind.PIECES)
    assert scan.parse_piece_sheet(text) == PUZZLE


@pytest.mark.spec("SPEC-0011", "AT-0008")
@pytest.mark.parametrize(
    ("client", "message"),
    [
        (StubClient("refusal", "", "cyber"), "the model declined (cyber)"),
        (StubClient("max_tokens", "{"), "the answer was cut off"),
        (StubClient("end_turn", "not json"), "the answer is not JSON"),
        (StubClient("end_turn", '{"name": 3}'), "the answer's border is not a dict"),
        (
            StubClient(
                "end_turn",
                json.dumps(
                    {
                        "name": "x",
                        "pieces": [],
                        "rows": "no",
                        "border": {s: "" for s in scan.BORDER_SIDES},
                    }
                ),
            ),
            "the answer's rows is not a list",
        ),
    ],
)
def test_claude_bad_answers(photos: list[Path], client: StubClient, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        model_with(client).read(photos, SheetKind.SOLVED)


@pytest.mark.spec("SPEC-0011", "AT-0008")
def test_unsupported_photo(tmp_path: Path) -> None:
    photo = tmp_path / "photo.heic"
    photo.write_bytes(b"x")
    with pytest.raises(ValueError, match="use a JPEG, PNG, GIF or WebP photo"):
        scan.image_block(photo)


class DecliningModel:
    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        raise ValueError("the model declined (cyber)")


@pytest.mark.spec("SPEC-0011", "AT-0008")
def test_failed_model_call_writes_nothing(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        run(["test_key", "photo.jpg"], DecliningModel(), workdir)
    assert stopped.value.code == 1
    assert "the model declined (cyber)" in capsys.readouterr().err
    assert not (workdir / "scans").exists()
