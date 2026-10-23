import pytest

from last_piece_puzzle.pieces import Bit, Piece, PieceSet, Tab
from last_piece_puzzle.puzzles.golfing_madness_puzzle import GOLFING_MADNESS_PIECES


@pytest.mark.spec("SPEC-0005", "AT-0002")
def test_placements_are_computed_once() -> None:
    piece = GOLFING_MADNESS_PIECES[0]
    assert piece.placements is piece.placements


@pytest.mark.spec("SPEC-0005", "AT-0003")
def test_search_order_is_n_to_a() -> None:
    pieces = PieceSet(GOLFING_MADNESS_PIECES)
    assert "".join(p.letter for p in pieces.search_order) == "NMLKJIHGFEDCBA"
    assert "".join(p.letter for p in pieces) == "ABCDEFGHIJKLMN"


@pytest.mark.spec("SPEC-0005", "AT-0003")
def test_lookup_size_and_cell_count() -> None:
    pieces = PieceSet(GOLFING_MADNESS_PIECES)
    assert pieces.by_letter["A"].name == "Bluehat"
    assert len(pieces) == 14
    assert pieces.cell_count == 64


@pytest.mark.spec("SPEC-0005", "AT-0003")
def test_duplicate_letter_raises() -> None:
    bit = Bit(0, 0, Tab.IN, Tab.IN, Tab.IN, Tab.IN)
    with pytest.raises(ValueError, match="letter"):
        PieceSet([Piece("A", "one", (bit,)), Piece("A", "two", (bit,))])
