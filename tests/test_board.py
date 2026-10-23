from pathlib import Path

import pytest

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Bit, Border, Tab
from last_piece_puzzle.puzzles.golfing_madness_puzzle import (
    GOLFING_MADNESS_BORDER,
    GOLFING_MADNESS_PIECES,
)
from last_piece_puzzle.solution import load_solution

FIXTURE = Path(__file__).parent / "fixtures" / "golfing_madness_solution_1.txt"
IN, OUT = Tab.IN, Tab.OUT
ONE_BY_TWO = Border(top=(IN, IN), left=(IN,), right=(IN,), bottom=(IN, IN))
CELL = Bit(0, 0, OUT, OUT, OUT, OUT)


@pytest.mark.spec("SPEC-0005", "AT-0004")
def test_place_then_remove_empties_board() -> None:
    board = Board(GOLFING_MADNESS_BORDER)
    placement = GOLFING_MADNESS_PIECES[0].placements[0]
    board.place("A", placement, 3, 3)
    assert board.cell(3, 3) == ("A", placement[0])
    board.remove(placement, 3, 3)
    assert board.grid() == ("........",) * 8
    assert board.first_free() == (0, 0)


@pytest.mark.spec("SPEC-0005", "AT-0004")
def test_first_free_and_is_full() -> None:
    board = Board(ONE_BY_TWO)
    assert board.first_free() == (0, 0)
    assert not board.is_full()
    board.place("A", (CELL,), 0, 0)
    assert board.first_free() == (0, 1)
    assert board.grid() == ("A.",)
    board.place("B", (CELL,), 0, 1)
    assert board.first_free() is None
    assert board.is_full()
    assert board.grid() == ("AB",)


@pytest.mark.spec("SPEC-0005", "AT-0004")
def test_from_grid_rebuilds_fixture() -> None:
    grid = load_solution(FIXTURE).grid
    board = Board.from_grid(GOLFING_MADNESS_PIECES, GOLFING_MADNESS_BORDER, grid)
    assert board is not None
    assert board.is_full()
    assert board.grid() == grid
