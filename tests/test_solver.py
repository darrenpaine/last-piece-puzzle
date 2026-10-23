from pathlib import Path

import pytest

from last_piece_puzzle import main, solver
from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import Solution, load_solution
from last_piece_puzzle.solver import SolveResult

FIXTURE = Path(__file__).parent / "fixtures" / "golfing_madness_solution_1.txt"
IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE
ALL_BITS = [bit for piece in PUZZLE.pieces for bit in piece.bits]


@pytest.mark.spec("SPEC-0003", "AT-0002")
@pytest.mark.spec("SPEC-0005", "AT-0001")
def test_rotate_four_times_gives_original() -> None:
    for bit in ALL_BITS:
        assert bit.rotated().rotated().rotated().rotated() == bit


@pytest.mark.spec("SPEC-0003", "AT-0002")
@pytest.mark.spec("SPEC-0005", "AT-0001")
def test_rotate_turns_clockwise() -> None:
    bit = Bit(1, 2, north=IN, west=OUT, south=NONE, east=IN)
    assert bit.rotated() == Bit(2, -1, north=OUT, west=NONE, south=IN, east=IN)


@pytest.mark.spec("SPEC-0003", "AT-0003")
@pytest.mark.spec("SPEC-0005", "AT-0001")
@pytest.mark.parametrize("piece", PUZZLE.pieces, ids=lambda p: p.letter)
def test_orientations_follow_cpp_order(piece: Piece) -> None:
    placements = piece.placements
    count = len(piece.bits)
    assert len(placements) == 4 * count
    bits = piece.bits
    for k in range(4):
        for j in range(count):
            placement = placements[k * count + j]
            anchor = placement[j]
            assert (anchor.row, anchor.col) == (0, 0)
            # Same shape and tabs as the rotated piece, only shifted.
            assert [(b.north, b.west, b.south, b.east) for b in placement] == [
                (b.north, b.west, b.south, b.east) for b in bits
            ]
            assert [(b.row - placement[0].row, b.col - placement[0].col) for b in placement] == [
                (b.row - bits[0].row, b.col - bits[0].col) for b in bits
            ]
        bits = tuple(b.rotated() for b in bits)


# A single bit whose tabs do not clash with the top-left corner (top[0] and left[0] are IN).
CORNER_OK = Bit(0, 0, north=OUT, west=OUT, south=IN, east=IN)


@pytest.mark.spec("SPEC-0003", "AT-0004")
@pytest.mark.spec("SPEC-0005", "AT-0001")
def test_fits_valid_placement() -> None:
    assert Board(PUZZLE.border).fits((CORNER_OK,), 0, 0)


@pytest.mark.spec("SPEC-0003", "AT-0004")
@pytest.mark.spec("SPEC-0005", "AT-0001")
@pytest.mark.parametrize(("row", "col"), [(0, 8), (8, 0), (-1, 0)])
def test_fits_rejects_off_board(row: int, col: int) -> None:
    assert not Board(PUZZLE.border).fits((CORNER_OK,), row, col)


@pytest.mark.spec("SPEC-0003", "AT-0004")
@pytest.mark.spec("SPEC-0005", "AT-0001")
def test_fits_rejects_overlap() -> None:
    board = Board(PUZZLE.border)
    board.place("A", (CORNER_OK,), 0, 0)
    assert not board.fits((CORNER_OK,), 0, 0)


@pytest.mark.spec("SPEC-0003", "AT-0004")
@pytest.mark.spec("SPEC-0005", "AT-0001")
def test_fits_rejects_border_clash() -> None:
    clash = Bit(0, 0, north=IN, west=OUT, south=IN, east=IN)  # top[0] is IN
    assert not Board(PUZZLE.border).fits((clash,), 0, 0)


@pytest.mark.spec("SPEC-0003", "AT-0004")
@pytest.mark.spec("SPEC-0005", "AT-0001")
@pytest.mark.parametrize(("east", "expected"), [(IN, False), (OUT, True)])
def test_fits_checks_neighbour_tab(east: Tab, expected: bool) -> None:
    board = Board(PUZZLE.border)
    board.place("B", (Bit(0, 0, north=OUT, west=IN, south=IN, east=IN),), 0, 1)
    bit = Bit(0, 0, north=OUT, west=OUT, south=IN, east=east)
    assert board.fits((bit,), 0, 0) is expected


@pytest.mark.spec("SPEC-0003", "B-0005")
@pytest.mark.parametrize(("tab", "solved"), [(OUT, True), (IN, False)])
def test_solve_one_cell_board(tab: Tab, solved: bool) -> None:
    border = Border(top=(IN,), left=(IN,), right=(IN,), bottom=(IN,))
    piece = Piece("A", "single", (Bit(0, 0, tab, tab, tab, tab),))
    result = solver.solve(Puzzle("one cell", (piece,), border))
    assert (result.solution is not None) is solved
    assert result.moves == (1 if solved else 0)
    if solved:
        assert result.solution == Solution(("A",))
        assert result.start_piece == "A"


@pytest.mark.spec("SPEC-0003", "AT-0005")
@pytest.mark.slow
def test_solve_matches_cpp() -> None:
    expected = load_solution(FIXTURE)
    result = solver.solve(PUZZLE)
    assert result.solution is not None
    assert result.solution.grid == expected.grid
    assert result.start_piece == expected.metadata["start_piece"]
    assert str(result.moves) == expected.metadata["moves"]


@pytest.mark.spec("SPEC-0003", "AT-0006")
def test_main_prints_grid_and_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    grid = load_solution(FIXTURE).grid
    monkeypatch.setattr(
        solver, "solve", lambda *args, **kwargs: SolveResult(Solution(grid), "E", 1529410)
    )
    main(["golfing_madness"])
    out = capsys.readouterr().out
    assert "Solution FOUND starting with piece E" in out
    assert "Board at Move 1529410:" in out
    assert "E E E H J J J J" in out
    assert "N = ZigZag" in out


@pytest.mark.spec("SPEC-0003", "AT-0006")
def test_main_reports_no_solution(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(solver, "solve", lambda *args, **kwargs: SolveResult(None, None, 42))
    main(["golfing_madness"])
    assert "Solution NOT Found in 42 Moves." in capsys.readouterr().out


ONE_BY_TWO = Border(top=(IN, IN), left=(IN,), right=(IN,), bottom=(IN, IN))
ALL_OUT = Bit(0, 0, OUT, OUT, OUT, OUT)


@pytest.mark.spec("SPEC-0003", "B-0005")
def test_solve_backtracks_and_counts_moves() -> None:
    # Two all-OUT bits clash with each other, so every start fails: per start piece,
    # 4 rotations x (place + remove) = 8 moves.
    pieces = (Piece("A", "a", (ALL_OUT,)), Piece("B", "b", (ALL_OUT,)))
    result = solver.solve(Puzzle("clash", pieces, ONE_BY_TWO))
    assert result.solution is None
    assert result.moves == 16


@pytest.mark.spec("SPEC-0003", "B-0005")
def test_solve_tries_pieces_in_reverse_and_rotates() -> None:
    # B is tried first and only fits at (0, 0) after 3 rotations (east tab IN); A then fits.
    b = Bit(0, 0, north=OUT, west=IN, south=OUT, east=OUT)
    pieces = (Piece("A", "a", (ALL_OUT,)), Piece("B", "b", (b,)))
    started: list[str] = []
    result = solver.solve(Puzzle("rotate", pieces, ONE_BY_TWO), on_start=started.append)
    assert result == SolveResult(Solution(("BA",)), "B", 2)
    assert started == ["B"]
