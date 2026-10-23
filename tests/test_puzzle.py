import pytest

from last_piece_puzzle import puzzles
from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE


def border(cols: int) -> Border:
    return Border(top=(IN,) * cols, left=(IN,), right=(IN,), bottom=(IN,) * cols)


def domino(*, left: Bit | None = None, right: Bit | None = None) -> Piece:
    return Piece(
        "A",
        "domino",
        (left or Bit(0, 0, OUT, OUT, OUT, NONE), right or Bit(0, 1, OUT, NONE, OUT, OUT)),
    )


SINGLE = Bit(0, 0, OUT, OUT, OUT, OUT)


@pytest.mark.spec("SPEC-0006", "AT-0001")
def test_valid_puzzle_passes() -> None:
    puzzle = Puzzle("domino", (domino(),), border(2))
    assert (puzzle.rows, puzzle.cols) == (1, 2)
    assert len(puzzle.piece_set) == 1


@pytest.mark.spec("SPEC-0006", "AT-0001")
@pytest.mark.parametrize(
    ("pieces", "frame", "message"),
    [
        ((Piece("A", "a", (SINGLE,)), Piece("A", "b", (SINGLE,))), border(2), "letter"),
        ((domino(),), Border((IN, IN), (IN,), (IN,), (IN,)), "lengths"),
        ((domino(),), Border((NONE, IN), (IN,), (IN,), (IN, IN)), "NONE"),
        ((Piece("A", "a", (SINGLE,)),), border(2), "cells"),
        ((Piece("A", "a", (SINGLE, SINGLE)),), border(2), "offset"),
        ((Piece("A", "a", (SINGLE, Bit(0, 2, OUT, OUT, OUT, OUT))),), border(2), "connected"),
        ((domino(left=Bit(0, 0, NONE, OUT, OUT, NONE)),), border(2), "no north tab"),
        ((domino(left=Bit(0, 0, OUT, OUT, OUT, OUT)),), border(2), "east tab facing itself"),
    ],
    ids=[
        "duplicate-letter",
        "border-lengths",
        "border-none",
        "cell-count",
        "same-offset",
        "disconnected",
        "none-facing-out",
        "tab-facing-own-bit",
    ],
)
def test_invalid_puzzle_raises(pieces: tuple[Piece, ...], frame: Border, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        Puzzle("bad", pieces, frame)


@pytest.mark.spec("SPEC-0006", "AT-0002")
def test_golfing_madness_puzzle() -> None:
    assert PUZZLE.name == "Golfing Madness"
    assert len(PUZZLE.pieces) == 14
    assert (PUZZLE.rows, PUZZLE.cols) == (8, 8)


@pytest.mark.spec("SPEC-0006", "AT-0003")
def test_available_and_load() -> None:
    assert "golfing_madness" in puzzles.available()
    assert puzzles.load("golfing_madness") is PUZZLE


@pytest.mark.spec("SPEC-0006", "AT-0003")
def test_load_unknown_lists_keys() -> None:
    with pytest.raises(ValueError, match="golfing_madness"):
        puzzles.load("nope")
