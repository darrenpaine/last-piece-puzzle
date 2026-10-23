from pathlib import Path

import pytest

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Piece
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import load_solution
from last_piece_puzzle.solver import check_solution

FIXTURE = Path(__file__).parent / "fixtures" / "golfing_madness_solution_1.txt"
GRID = load_solution(FIXTURE).grid
BORDER = PUZZLE.border


def check(grid: list[str] | tuple[str, ...]) -> bool:
    return check_solution(PUZZLE, grid)


def swap_letters(grid: tuple[str, ...], a: str, b: str) -> list[str]:
    return [row.translate(str.maketrans(a + b, b + a)) for row in grid]


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
@pytest.mark.spec("SPEC-0005", "AT-0001")
@pytest.mark.parametrize("piece", PUZZLE.pieces, ids=lambda p: p.letter)
def test_only_correct_placement_fits_gap(piece: Piece) -> None:
    board = Board.from_grid(PUZZLE, GRID)
    assert board is not None
    placed = [
        (r, c, cell[1])
        for r in range(board.rows)
        for c in range(board.cols)
        if (cell := board.cell(r, c)) is not None and cell[0] == piece.letter
    ]
    correct = {(r, c, b.north, b.west, b.south, b.east) for r, c, b in placed}
    # Each placed bit keeps its offset from the anchor, so any one of them locates the anchor.
    r, c, bit = placed[0]
    board.remove(tuple(b for _, _, b in placed), r - bit.row, c - bit.col)
    fitting = {
        frozenset((row + b.row, col + b.col, b.north, b.west, b.south, b.east) for b in placement)
        for placement in piece.placements
        for row in range(board.rows)
        for col in range(board.cols)
        if board.fits(placement, row, col)
    }
    # D and H look the same after a 180 degree turn, tabs included, so compare distinct placements.
    assert fitting == {frozenset(correct)}
