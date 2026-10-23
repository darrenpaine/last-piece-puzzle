from pathlib import Path

import pytest

from last_piece_puzzle import solver
from last_piece_puzzle.pieces import Piece
from last_piece_puzzle.puzzles.golfing_madness_puzzle import (
    GOLFING_MADNESS_BORDER,
    GOLFING_MADNESS_PIECES,
)
from last_piece_puzzle.solution import load_solution
from last_piece_puzzle.solver import build_board, check_solution, fits, orientations

FIXTURE = Path(__file__).parent / "fixtures" / "golfing_madness_solution_1.txt"
GRID = load_solution(FIXTURE).grid
PIECES = GOLFING_MADNESS_PIECES
BORDER = GOLFING_MADNESS_BORDER


def check(grid: list[str] | tuple[str, ...]) -> bool:
    return check_solution(PIECES, BORDER, grid)


def swap_letters(grid: tuple[str, ...], a: str, b: str) -> list[str]:
    return [row.translate(str.maketrans(a + b, b + a)) for row in grid]


@pytest.mark.spec("SPEC-0004", "AT-0001")
def test_seeded_start_finds_cpp_solution() -> None:
    started: list[str] = []
    result = solver.solve(PIECES, BORDER, start_pieces=["E"], on_start=started.append)
    assert result.solution is not None
    assert result.solution.grid == GRID
    assert result.start_piece == "E"
    assert result.moves == 332262
    assert started == ["E"]


@pytest.mark.spec("SPEC-0004", "AT-0002")
def test_check_accepts_fixture() -> None:
    assert check(GRID)


@pytest.mark.spec("SPEC-0004", "AT-0003")
@pytest.mark.parametrize(
    "grid",
    [
        [row[::-1] for row in GRID[::-1]],
        [row[::-1] for row in GRID],
        list(GRID[::-1]),
        swap_letters(GRID, "A", "E"),
        swap_letters(GRID, "G", "H"),
        [GRID[0].replace("E", "Z", 1), *GRID[1:]],
        [row.replace("B", "A") for row in GRID],
        # Swap the cells at (0, 3) H and (0, 4) J, so neither keeps its shape.
        ["EEEJHJJJ", *GRID[1:]],
        GRID[:7],
    ],
    ids=[
        "rotated-180",
        "mirrored",
        "flipped",
        "swap-A-E",
        "swap-G-H",
        "unknown-letter",
        "missing-piece",
        "wrong-shape",
        "short-grid",
    ],
)
def test_check_rejects_wrong_grids(grid: list[str]) -> None:
    assert not check(grid)


@pytest.mark.spec("SPEC-0004", "AT-0004")
@pytest.mark.parametrize("piece", PIECES, ids=lambda p: p.letter)
def test_only_correct_placement_fits_gap(piece: Piece) -> None:
    board = build_board(PIECES, BORDER, GRID)
    assert board is not None
    correct = {
        (r, c, cell[1].north, cell[1].west, cell[1].south, cell[1].east)
        for r, row in enumerate(board)
        for c, cell in enumerate(row)
        if cell is not None and cell[0] == piece.letter
    }
    for r, c, *_ in correct:
        board[r][c] = None
    fitting = {
        frozenset((row + b.row, col + b.col, b.north, b.west, b.south, b.east) for b in placement)
        for placement in orientations(piece)
        for row in range(len(board))
        for col in range(len(board[0]))
        if fits(board, BORDER, placement, row, col)
    }
    # D and H look the same after a 180 degree turn, tabs included, so compare distinct placements.
    assert fitting == {frozenset(correct)}


@pytest.mark.spec("SPEC-0004", "AT-0005")
@pytest.mark.slow
def test_only_a_c_e_start_a_solution() -> None:
    solved = {}
    for piece in PIECES:
        result = solver.solve(PIECES, BORDER, start_pieces=[piece.letter])
        if result.solution is not None:
            solved[piece.letter] = result.solution.grid
    assert solved.keys() == {"A", "C", "E"}
    assert solved["E"] == GRID
    for grid in solved.values():
        assert check(grid)
