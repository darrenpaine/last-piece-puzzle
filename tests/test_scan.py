import dataclasses
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import cast

import anthropic
import httpx
import httpx2
import pytest
from google import genai
from google.genai._gaos.lib import compat_errors
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


def tabs_at(board: SolvedBoard, row: int, col: int) -> scan.Tabs:
    cell = board.cells[row][col]
    assert cell is not None
    return cell[1]


def with_tab(board: SolvedBoard, row: int, col: int, side: int, tab: Tab) -> SolvedBoard:
    """The board with one side of one cell changed."""
    cells = [list(line) for line in board.cells]
    cell = cells[row][col]
    assert cell is not None
    letter, tabs = cell
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
    return {found.solution.grid for found in solver.solve(puzzle, method="exactcover").solutions}


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
    same_as_cell = scan.TAB_CHARS[tabs_at(board, 0, 0)[0]]
    east_of_e = tabs_at(board, 0, 2)[3]
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
        for c in range(len(row)):
            for k, tab in enumerate(tabs_at(board, r, c)):
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


@pytest.mark.spec("SPEC-0011", "AT-0015")
def test_scan_prints_progress(workdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(["test_key", "photo.jpg"], FakeModel(scan.format_solved_sheet(solved_board())), workdir)
    out, err = capsys.readouterr()
    lines = err.splitlines()
    assert lines[0] == f"[0:00:00] Reading 1 photo with {scan.MODEL} (solved)"
    assert [line.split("] ", 1)[1] for line in lines[1:]] == [
        f"{scan.MODEL} answered",
        f"Checking {Path('scans/test_key/sheet.txt')}",
        "Solving (Algorithm X)",
        "Solved",
    ]
    assert "[" not in out


@pytest.mark.spec("SPEC-0011", "AT-0015")
def test_progress_prints_still_waiting(capsys: pytest.CaptureFixture[str]) -> None:
    beat = threading.Event()

    def status() -> str:
        beat.set()
        return "3 so far"

    with scan.Progress().waiting("the model", status, every=0.01):
        assert beat.wait(5)
    assert "] Still waiting for the model (3 so far)" in capsys.readouterr().err


@pytest.mark.spec("SPEC-0011", "AT-0005")
def test_pieces_option_asks_for_a_piece_sheet(workdir: Path) -> None:
    model = FakeModel(scan.format_piece_sheet(PUZZLE))
    run(["test_key", "a.jpg", "b.jpg", "--pieces"], model, workdir)
    assert model.calls == [([Path("a.jpg"), Path("b.jpg")], SheetKind.PIECES)]
    assert load_module(workdir / "puzzles" / "test_key_puzzle.py").PUZZLE == PUZZLE


def failing_sheets() -> list[tuple[str, list[str], str]]:
    board = solved_board()
    clash = scan.format_solved_sheet(with_tab(board, 0, 2, 3, FLIP[tabs_at(board, 0, 2)[3]]))
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
    def __init__(
        self,
        stop_reason: str,
        text: str,
        category: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.error = error
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
        if self.error:
            raise self.error
        return self

    def __enter__(self) -> StubClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get_final_message(self) -> SimpleNamespace:
        return self.message


def model_with(client: StubClient) -> scan.ClaudeVisionModel:
    return scan.ClaudeVisionModel(cast(anthropic.Anthropic, client))


def board_json(board: SolvedBoard) -> str:
    """A model's JSON answer for a solved board, or an unsolved one (gaps and loose pieces)."""
    chars = scan.TAB_CHARS
    sides = [side for side, _, _ in scan.CELL_SIDES]
    loose = {piece.letter for piece in board.loose}

    def cell_json(cell: scan.BoardCell) -> dict[str, str]:
        letter, tabs = cell or (".", (Tab.NONE,) * 4)
        return {"letter": letter, **{s: chars[t] for s, t in zip(sides, tabs, strict=True)}}

    answer: dict[str, object] = {
        "name": board.name,
        "pieces": [{"letter": k, "name": v} for k, v in board.names.items() if k not in loose],
        "rows": [[cell_json(cell) for cell in row] for row in board.cells],
        "border": {
            side: "".join(chars[t] for t in getattr(board.border, side))
            for side in scan.BORDER_SIDES
        },
    }
    if board.loose:
        answer["loose"] = [piece_json(piece) for piece in board.loose]
    return json.dumps(answer)


def piece_json(piece: Piece) -> dict[str, object]:
    chars = scan.TAB_CHARS
    sides = [side for side, _, _ in scan.CELL_SIDES]
    return {
        "letter": piece.letter,
        "name": piece.name,
        "cells": [
            {
                "row": b.row,
                "col": b.col,
                **{s: chars[t] for s, t in zip(sides, scan.bit_tabs(b), strict=True)},
            }
            for b in piece.bits
        ],
    }


def pieces_json(puzzle: Puzzle) -> str:
    return json.dumps(
        {
            "name": puzzle.name,
            "border": {
                side: "".join(scan.TAB_CHARS[t] for t in getattr(puzzle.border, side))
                for side in scan.BORDER_SIDES
            },
            "pieces": [piece_json(piece) for piece in puzzle.pieces],
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
    client = StubClient("end_turn", board_json(solved_board()))
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


@pytest.mark.spec("SPEC-0011", "AT-0008")
def test_claude_api_error(photos: list[Path]) -> None:
    error = anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com")
    )
    with pytest.raises(ValueError, match="Claude API error: Connection error"):
        model_with(StubClient("end_turn", "", error=error)).read(photos, SheetKind.SOLVED)


# Unsolved sheets: the puzzle as sold, with a gap and the last piece outside the board


def unsolved_board(letter: str = "B") -> SolvedBoard:
    """Fixture 1 with one piece taken out: its cells become the gap, and it is listed as loose."""
    board = solved_board()
    piece = next(p for p in board.to_puzzle().pieces if p.letter == letter)
    cells = tuple(
        tuple(None if cell and cell[0] == letter else cell for cell in row) for row in board.cells
    )
    return dataclasses.replace(board, cells=cells, loose=(piece,))


@pytest.mark.spec("SPEC-0011", "AT-0009")
def test_unsolved_sheet_gives_golfing_madness() -> None:
    text = scan.format_solved_sheet(unsolved_board())
    assert "piece B: Purple Pants\n  0,0 " in text
    assert scan.sheet_kind(text) is SheetKind.UNSOLVED
    board = scan.parse_solved_sheet(text)
    assert board == unsolved_board()
    assert board.gaps == [(6, 6), (7, 6), (7, 7)]
    assert board.grid.grid[7] == "AAAIII.."
    puzzle = board.to_puzzle()
    assert [p.letter for p in puzzle.pieces] == [p.letter for p in PUZZLE.pieces]
    for piece, expected in zip(puzzle.pieces, PUZZLE.pieces, strict=True):
        assert canonical(piece) == canonical(expected)
    assert puzzle.border == PUZZLE.border
    assert scan.tab_balance(puzzle) == 0
    assert grids(puzzle) == set(GRIDS)


@pytest.mark.spec("SPEC-0011", "AT-0009")
def test_sheet_kinds() -> None:
    assert scan.sheet_kind(scan.format_solved_sheet(solved_board())) is SheetKind.SOLVED
    assert scan.sheet_kind(scan.format_piece_sheet(PUZZLE)) is SheetKind.PIECES


def bad_unsolved_sheets() -> list[tuple[str, str]]:
    board = unsolved_board()  # B's cells (6, 6), (7, 6) and (7, 7) are the gap
    text = scan.format_solved_sheet(board)
    cell_lines = [line for line in text.splitlines(keepends=True) if line.startswith("  ")]
    on_board_too = text.replace(
        "piece E: Redhead red Pants\n", "piece E: Redhead red Pants\n  0,0 OO-O\n"
    )
    return [
        (
            scan.format_solved_sheet(with_tab(board, 6, 5, 3, Tab.NONE)),
            "cell (6, 5) D east: - faces the gap",
        ),
        (without_border(text), "no top line: an unsolved sheet needs the whole frame"),
        (text.replace(cell_lines[-1], "", 1), "the loose pieces have 2 cells, the gap has 3"),
        (
            "".join(line for line in text.splitlines(keepends=True) if line not in cell_lines),
            "3 gap cells but no loose piece",
        ),
        (on_board_too, "cell (0, 0): piece E is loose but on the board"),
    ]


@pytest.mark.spec("SPEC-0011", "AT-0010")
@pytest.mark.parametrize(
    ("text", "message"), [pytest.param(*case, id=case[1]) for case in bad_unsolved_sheets()]
)
def test_bad_unsolved_sheet(text: str, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(message)}"):
        scan.parse_solved_sheet(text)


@pytest.mark.spec("SPEC-0011", "AT-0011")
def test_unsolved_option_writes_module(workdir: Path) -> None:
    model = FakeModel(scan.format_solved_sheet(unsolved_board()))
    run(["test_key", "photo.jpg", "--unsolved"], model, workdir)
    assert model.calls == [([Path("photo.jpg")], SheetKind.UNSOLVED)]
    assert grids(load_module(workdir / "puzzles" / "test_key_puzzle.py").PUZZLE) == set(GRIDS)


@pytest.mark.spec("SPEC-0011", "AT-0011")
def test_unsolved_sheet_with_a_flipped_loose_tab_stops_at_tab_balance(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    board = unsolved_board()
    [piece] = board.loose
    first = piece.bits[0]
    k = next(k for k, tab in enumerate(scan.bit_tabs(first)) if tab is not Tab.NONE)
    tabs = list(scan.bit_tabs(first))
    tabs[k] = FLIP[tabs[k]]
    flipped = dataclasses.replace(piece, bits=(Bit(first.row, first.col, *tabs), *piece.bits[1:]))
    text = scan.format_solved_sheet(dataclasses.replace(board, loose=(flipped,)))
    with pytest.raises(SystemExit):
        run(["test_key", "photo.jpg", "--unsolved"], FakeModel(text), workdir)
    assert "tabs don't balance" in capsys.readouterr().err
    assert not (workdir / "puzzles" / "test_key_puzzle.py").exists()


@pytest.mark.spec("SPEC-0011", "AT-0011")
def test_pieces_and_unsolved_together_are_refused(workdir: Path) -> None:
    with pytest.raises(SystemExit) as stopped:
        run(["test_key", "photo.jpg", "--pieces", "--unsolved"], NoModel(), workdir)
    assert stopped.value.code == 2


@pytest.mark.spec("SPEC-0011", "AT-0011")
def test_claude_unsolved_answer(photos: list[Path]) -> None:
    expected = unsolved_board()
    text = model_with(StubClient("end_turn", board_json(expected))).read(photos, SheetKind.UNSOLVED)
    board = scan.parse_solved_sheet(text)
    assert (board.cells, board.loose, board.border) == (
        expected.cells,
        expected.loose,
        expected.border,
    )
    assert board.names.items() == expected.names.items()


# The checkerboard report and the warning about many solutions


@pytest.mark.spec("SPEC-0011", "AT-0012")
def test_pattern_breaks_in_golfing_madness() -> None:
    puzzle, board = scan.check_sheet(scan.format_solved_sheet(solved_board()))
    assert scan.pattern_breaks(puzzle, board) == ["cell (7, 6) B south is O"]
    assert scan.pattern_breaks(PUZZLE) == ["bottom tab 6 is I", "piece B cell 0,1 east is O"]
    puzzle, board = scan.check_sheet(scan.format_solved_sheet(unsolved_board()))
    assert scan.pattern_breaks(puzzle, board) == [
        "bottom tab 6 (at the gap) is I",
        "piece B cell 1,0 south is O",  # B as it lay on the board
    ]


@pytest.mark.spec("SPEC-0011", "AT-0012")
def test_report_and_warning(
    workdir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    good = workdir / "good.txt"
    good.write_text(scan.format_solved_sheet(solved_board()))
    run(["good", "--sheet", str(good)], NoModel(), workdir)
    out = capsys.readouterr().out
    assert "checkerboard (1)" in out and "cell (7, 6) B south is O" in out
    assert "Warning" not in out

    monkeypatch.setattr(scan, "MANY_SOLUTIONS", 4)
    run(["good", "--sheet", str(good), "--force"], NoModel(), workdir)
    assert "Warning: 5 solutions" in capsys.readouterr().out


@pytest.mark.slow
@pytest.mark.spec("SPEC-0011", "AT-0012")
def test_report_and_warning_for_the_trial_sheet(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    trial = ROOT / "scans" / "golfing_madness_scan" / "sheet.txt"  # the blind trial's sheet
    run(["trial", "--sheet", str(trial)], NoModel(), workdir)
    out = capsys.readouterr().out
    assert "1614 solutions found." in out
    assert "cell (7, 6) O south is O" in out and "cell (7, 7) O south is I" in out
    assert "Warning: 1614 solutions" in out


# Gemini, with the SDK client replaced by a stub


class StubGemini:
    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self.text, self.error = text, error
        self.requests: list[dict[str, object]] = []
        self.interactions = SimpleNamespace(create=self.create)

    def create(self, **request: object) -> SimpleNamespace:
        self.requests.append(request)
        if self.error:
            raise self.error
        return SimpleNamespace(output_text=self.text)


def gemini_with(client: StubGemini, model: str = scan.GEMINI_MODEL) -> scan.GeminiVisionModel:
    return scan.GeminiVisionModel(cast(genai.Client, client), model)


@pytest.mark.spec("SPEC-0011", "AT-0013")
def test_gemini_request_and_answer(photos: list[Path]) -> None:
    client = StubGemini(board_json(solved_board()))
    text = gemini_with(client, "gemini-3.8-flash").read(photos, SheetKind.SOLVED)
    assert text == scan.format_solved_sheet(solved_board())
    [request] = client.requests
    assert request["model"] == "gemini-3.8-flash"
    assert request["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": scan.SCHEMAS[SheetKind.SOLVED],
    }
    items = cast(list[dict[str, str]], request["input"])
    assert [item["mime_type"] for item in items[:-1]] == ["image/jpeg", "image/png"]
    assert all(item["type"] == "image" and item["data"] for item in items[:-1])
    assert items[-1] == {"type": "text", "text": scan.PROMPTS[SheetKind.SOLVED]}


@pytest.mark.spec("SPEC-0011", "AT-0013")
@pytest.mark.parametrize(
    ("client", "message"),
    [
        (StubGemini(None), "the answer has no text"),
        (StubGemini("not json"), "the answer is not JSON"),
        (StubGemini('{"name": 3}'), "the answer's border is not a dict"),
        (
            StubGemini(error=genai.errors.APIError(503, {"error": {"status": "UNAVAILABLE"}})),
            "Gemini API error: 503",
        ),
    ],
)
def test_gemini_bad_answers(photos: list[Path], client: StubGemini, message: str) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        gemini_with(client).read(photos, SheetKind.SOLVED)


@pytest.mark.spec("SPEC-0011", "AT-0016")
def test_gemini_client_has_timeout(photos: list[Path], monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[genai.types.HttpOptions] = []

    def client(http_options: genai.types.HttpOptions) -> StubGemini:
        built.append(http_options)
        return StubGemini(board_json(solved_board()))

    monkeypatch.setattr(genai, "Client", client)
    scan.GeminiVisionModel().read(photos, SheetKind.SOLVED)
    assert [options.timeout for options in built] == [scan.GEMINI_TIMEOUT_SECONDS * 1000]


def timeout() -> compat_errors.APITimeoutError:
    return compat_errors.APITimeoutError(httpx.Request("POST", "https://example.com"))


class FlakyGemini(StubGemini):
    """Times out on the first `failures` requests, then answers."""

    def __init__(self, failures: int) -> None:
        super().__init__(board_json(solved_board()))
        self.failures = failures

    def create(self, **request: object) -> SimpleNamespace:
        if len(self.requests) < self.failures:
            self.requests.append(request)
            raise timeout()
        return super().create(**request)


@pytest.mark.spec("SPEC-0011", "AT-0016")
def test_gemini_retries_timeouts(
    photos: list[Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    waits: list[float] = []
    monkeypatch.setattr(time, "sleep", waits.append)
    client = FlakyGemini(failures=2)
    assert gemini_with(client).read(photos, SheetKind.SOLVED) == scan.format_solved_sheet(
        solved_board()
    )
    assert len(client.requests) == 3
    assert waits == [30, 60]
    assert "APITimeoutError" in capsys.readouterr().err

    client = FlakyGemini(failures=3)
    with pytest.raises(ValueError, match=r"Gemini request failed: APITimeoutError.*\(3 tries\)"):
        gemini_with(client).read(photos, SheetKind.SOLVED)
    assert len(client.requests) == 3


@pytest.mark.spec("SPEC-0011", "AT-0016")
def test_gemini_interactions_error_status(photos: list[Path]) -> None:
    request = httpx.Request("POST", "https://example.com")
    body = {"error": {"status": "UNAVAILABLE"}}
    response = httpx.Response(503, request=request)
    error = compat_errors.APIError.generate(503, body, None, response)
    client = StubGemini(error=error)
    with pytest.raises(ValueError, match="Gemini API error: "):
        gemini_with(client).read(photos, SheetKind.SOLVED)
    assert len(client.requests) == 1


class RecordingModel:
    """Stands in for a model class, recording how the CLI built it."""

    built: list[dict[str, object]] = []

    def __init__(self, **options: object) -> None:
        RecordingModel.built.append(options)

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        return scan.format_solved_sheet(solved_board())


@pytest.mark.spec("SPEC-0011", "AT-0013")
@pytest.mark.parametrize(
    ("options", "patched", "built"),
    [
        ([], "ClaudeVisionModel", {}),
        (["--model", "gemini"], "GeminiVisionModel", {"model": scan.GEMINI_MODEL}),
        (
            ["--model", "gemini", "--gemini-model", "gemini-3.8-flash"],
            "GeminiVisionModel",
            {"model": "gemini-3.8-flash"},
        ),
    ],
)
def test_cli_picks_the_model(
    workdir: Path,
    monkeypatch: pytest.MonkeyPatch,
    options: list[str],
    patched: str,
    built: dict[str, object],
) -> None:
    RecordingModel.built = []
    monkeypatch.setattr(scan, patched, RecordingModel)
    scan.main(["test_key", "photo.jpg", *options], puzzles_dir=workdir / "puzzles")
    assert RecordingModel.built == [built]


# Puzzling Pets as sold: one pair of inneys touches, between an edge piece and the frame

PETS = ROOT / "scans" / "puzzling_pets" / "sheet_claude.txt"


@pytest.mark.spec("SPEC-0011", "AT-0014")
def test_puzzling_pets_sheet(workdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    board = scan.parse_solved_sheet(PETS.read_text())
    assert scan.touching_inneys(board) == ["bottom tab 6 and cell (7, 6) M south"]
    run(["pets", "--sheet", str(PETS)], NoModel(), workdir)
    out = capsys.readouterr().out
    assert "5 solutions found." in out
    assert "bottom tab 6 is I" in out and "piece N cell 1,0 east is O" in out
    assert "Inneys that touch as sold: bottom tab 6 and cell (7, 6) M south" in out
    assert "Warning" not in out
    assert len(grids(load_module(workdir / "puzzles" / "pets_puzzle.py").PUZZLE)) == 5


@pytest.mark.spec("SPEC-0011", "AT-0014")
def test_unsolved_sheet_still_rejects_touching_outeys() -> None:
    text = PETS.read_text().replace("bottom: OIOIOIII", "bottom: OIOIOIOI")
    assert scan.parse_solved_sheet(text)  # the frame's outey meets the cell's inney: fine
    clash = PETS.read_text().replace("M:I-II K:-OOO", "M:I-OI K:-OOO")  # (7, 6) south O
    message = "bottom tab 6 is O and cell (7, 6) M south is O: touching tabs must differ"
    with pytest.raises(ValueError, match=re.escape(message)):
        scan.parse_solved_sheet(clash.replace("bottom: OIOIOIII", "bottom: OIOIOIOI"))
    with pytest.raises(ValueError, match="no top line"):
        scan.parse_solved_sheet(without_border(PETS.read_text()))


@pytest.mark.spec("SPEC-0011", "AT-0014")
def test_inneys_inside_the_board_are_allowed_but_warned(
    workdir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    board = unsolved_board()  # fixture 1 has no touching inneys at all
    assert scan.touching_inneys(board) == []
    sheet = workdir / "sheet.txt"
    sheet.write_text(scan.format_solved_sheet(board))
    run(["golf", "--sheet", str(sheet)], NoModel(), workdir)
    out = capsys.readouterr().out
    assert "Inneys that touch as sold: none" in out
    assert "Warning: as sold, these puzzles have exactly one pair of touching inneys" in out
    inside = with_tab(board, 0, 2, 3, Tab.IN)  # E's east inney now meets H's west inney
    assert scan.touching_inneys(scan.parse_solved_sheet(scan.format_solved_sheet(inside))) == [
        "cell (0, 2) E east and cell (0, 3) H west"
    ]


# Flight of Fancy from loose pieces: the sheet Claude Code read, checked against the pieces

FLIGHT = ROOT / "scans" / "flight_of_fancy"


@pytest.mark.spec("SPEC-0011", "AT-0017")
def test_flight_of_fancy_sheet(workdir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(["flight_of_fancy", "--sheet", str(FLIGHT / "sheet_claude.txt")], NoModel(), workdir)
    out = capsys.readouterr().out
    assert "5 solutions found." in out
    assert "bottom tab 6 is I" in out and "piece A cell 0,0 west is O" in out
    assert "Warning" not in out
    module = workdir / "puzzles" / "flight_of_fancy_puzzle.py"
    committed = ROOT / "src" / "last_piece_puzzle" / "puzzles" / "flight_of_fancy_puzzle.py"
    assert module.read_text() == committed.read_text()
    assert (workdir / "scans" / "flight_of_fancy" / "pieces.txt").read_text() == (
        FLIGHT / "pieces.txt"
    ).read_text()
    assert len(grids(load_module(module).PUZZLE)) == 5
