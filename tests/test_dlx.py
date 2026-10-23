import re
from pathlib import Path

import pytest
from test_parallel import SMALL_PUZZLES

from last_piece_puzzle import main, solver
from last_piece_puzzle.board import Board
from last_piece_puzzle.dlx import CoverTable, DlxSolver, bits
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import Solution, load_solution
from last_piece_puzzle.solver import FoundSolution, SolveResult

GRIDS = [
    load_solution(Path(__file__).parent / "fixtures" / f"golfing_madness_solution_{n}.txt").grid
    for n in range(1, 6)
]
TABLE = CoverTable(PUZZLE)


def grids(result: SolveResult) -> list[tuple[str, ...]]:
    return [found.solution.grid for found in result.solutions]


@pytest.mark.spec("SPEC-0010", "AT-0001")
def test_golfing_madness_gives_fixtures_in_order() -> None:
    numbered: list[tuple[int, FoundSolution]] = []
    result = solver.solve(PUZZLE, on_solution=lambda n, f: numbered.append((n, f)), method="dlx")
    assert grids(result) == GRIDS
    assert [found.start_piece for found in result.solutions] == list("EECCA")
    assert all(found.times_found == 1 for found in result.solutions)
    assert result.boards_found == 5
    assert numbered == list(enumerate(result.solutions, start=1))


@pytest.mark.spec("SPEC-0010", "AT-0001")
def test_moves_count_rows_chosen() -> None:
    result = DlxSolver(PUZZLE).solve()
    assert result.moves == 19469
    assert all(0 < found.found_at_move <= result.moves for found in result.solutions)


@pytest.mark.spec("SPEC-0010", "AT-0002")
@pytest.mark.parametrize(("start", "expected"), [("E", GRIDS[:2]), ("M", [])])
def test_start_pieces(start: str, expected: list[tuple[str, ...]]) -> None:
    started: list[str] = []
    result = solver.solve(PUZZLE, [start], on_start=started.append, method="dlx")
    assert grids(result) == expected
    assert started == [start]


@pytest.mark.spec("SPEC-0010", "AT-0003")
@pytest.mark.parametrize("all_rotations", [False, True])
@pytest.mark.parametrize("key", sorted(SMALL_PUZZLES))
def test_small_puzzles_match_search(key: str, all_rotations: bool) -> None:
    puzzle: Puzzle = SMALL_PUZZLES[key]
    started: list[str] = []
    dfs_started: list[str] = []
    dlx = solver.solve(puzzle, on_start=started.append, all_rotations=all_rotations, method="dlx")
    dfs = solver.solve(puzzle, on_start=dfs_started.append)
    assert grids(dlx) == grids(dfs)
    assert [f.start_piece for f in dlx.solutions] == [f.start_piece for f in dfs.solutions]
    assert started == dfs_started
    assert dlx.boards_found == len(dlx.solutions)


@pytest.mark.spec("SPEC-0010", "AT-0004")
def test_cover_table_rows_mark_cells_and_piece() -> None:
    assert len(TABLE.rows) == 1419
    pieces = {piece.letter: 64 + k for k, piece in enumerate(PUZZLE.pieces)}
    for i, row in enumerate(TABLE.rows):
        marked = {r * 8 + c for r, c in row.cells} | {pieces[row.letter]}
        assert set(bits(TABLE.covers[i])) == marked
        assert all(TABLE.columns[k] >> i & 1 for k in marked)
    assert sum(mask.bit_count() for mask in TABLE.columns) == sum(
        mask.bit_count() for mask in TABLE.covers
    )


def solution_row(letter: str, grid: tuple[str, ...]) -> int:
    """The one table row that puts `letter` where `grid` has it, with tabs fitting the grid."""
    board = Board.from_grid(PUZZLE, grid)
    assert board is not None
    matches = [
        i
        for i, row in enumerate(TABLE.rows)
        if all(
            board.cell(r, c) == (letter, bit)
            for (r, c), bit in zip(row.cells, row.placement, strict=True)
        )
    ]
    assert len(matches) == 1
    return matches[0]


@pytest.mark.spec("SPEC-0010", "AT-0004")
def test_cover_table_excludes() -> None:
    # In fixture _1, E fills the top-left corner and H touches it on the right and below.
    e, h = solution_row("E", GRIDS[0]), solution_row("H", GRIDS[0])
    assert not TABLE.excludes[e] >> h & 1
    assert not TABLE.excludes[h] >> e & 1
    # E's excludes are exactly the rows that reuse E or no longer fit next to it on a board.
    board = Board(PUZZLE.border)
    placed = TABLE.rows[e]
    board.place(placed.letter, placed.placement, placed.row, placed.col)
    clashes = 0
    for i, row in enumerate(TABLE.rows):
        overlaps = row.letter == "E" or bool(set(row.cells) & set(placed.cells))
        fits = board.fits(row.placement, row.row, row.col)
        assert bool(TABLE.excludes[e] >> i & 1) == (overlaps or not fits)
        clashes += not overlaps and not fits
    assert clashes > 0


@pytest.mark.spec("SPEC-0010", "AT-0006")
def test_solve_defaults_to_search() -> None:
    result = solver.solve(SMALL_PUZZLES["two-solutions"])
    assert result.moves == 8  # DFS counts every place and remove
    assert solver.solve(SMALL_PUZZLES["two-solutions"], method="dlx").moves == 4  # rows chosen


DLX_LINE = r"1 solution found in 7 rows chosen, \d+\.\d s \(DLX\)\."
SEARCH_LINE = r"1 solution found in 7 moves, \d+\.\d s \(\d+ workers?\)\."


@pytest.fixture
def methods(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """Stub the solver with one solution found in 7 steps; record the method asked for."""
    seen: list[object] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        seen.append(kwargs.get("method"))
        return SolveResult((FoundSolution(Solution(("A",)), "A", 1),), 1, 7)

    monkeypatch.setattr(solver, "solve", fake_solve)
    return seen


@pytest.mark.spec("SPEC-0010", "AT-0005")
@pytest.mark.parametrize(
    ("argv", "method", "last_line"),
    [
        (["--method", "dlx"], "dlx", DLX_LINE),
        (["--method", "search"], "search", SEARCH_LINE),
    ],
)
def test_cli_method(
    methods: list[object],
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    method: str,
    last_line: str,
) -> None:
    main(["golfing_madness", *argv])
    assert methods == [method]
    assert re.fullmatch(last_line, capsys.readouterr().out.splitlines()[-1])


@pytest.mark.spec("SPEC-0010", "AT-0005")
def test_cli_dlx_no_solutions_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(solver, "solve", lambda *args, **kwargs: SolveResult((), 0, 3))
    main(["golfing_madness", "--method", "dlx"])
    last = capsys.readouterr().out.splitlines()[-1]
    assert re.fullmatch(r"No solutions found in 3 rows chosen, \d+\.\d s \(DLX\)\.", last)


@pytest.mark.spec("SPEC-0010", "AT-0005")
def test_cli_unknown_method_exits_2(
    methods: list[object], capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["golfing_madness", "--method", "nope"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
    assert methods == []
