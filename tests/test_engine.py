import pytest

from last_piece_puzzle.board import Board
from last_piece_puzzle.engine import EAST, NORTH, SOUTH, WEST, Candidates, Check
from last_piece_puzzle.pieces import Piece, Placement, Tab
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE

CELLS = [(0, 0), (3, 4), (PUZZLE.rows - 1, PUZZLE.cols - 1)]
CANDIDATES = {mode: Candidates(PUZZLE, all_rotations=mode) for mode in (False, True)}
# Each side of a bit: the offset of the cell it faces, and the index of that cell's facing side.
SIDES = {
    "north": (-1, 0, SOUTH),
    "west": (0, -1, EAST),
    "south": (1, 0, NORTH),
    "east": (0, 1, WEST),
}


def placements_of(piece: Piece, all_rotations: bool) -> tuple[Placement, ...]:
    return piece.placements if all_rotations else piece.distinct_placements


@pytest.mark.spec("SPEC-0009", "AT-0002")
@pytest.mark.parametrize("all_rotations", [False, True])
@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("piece", PUZZLE.pieces, ids=lambda p: p.letter)
def test_candidates_are_placements_that_fit_an_empty_board(
    piece: Piece, cell: tuple[int, int], all_rotations: bool
) -> None:
    board = Board(PUZZLE.border)
    expected = [
        index
        for index, placement in enumerate(placements_of(piece, all_rotations))
        if board.fits(placement, *cell)
    ]
    found = CANDIDATES[all_rotations].at(*cell, piece.letter)
    assert [candidate.placement_index for candidate in found] == expected


@pytest.mark.spec("SPEC-0009", "AT-0003")
@pytest.mark.parametrize("all_rotations", [False, True])
@pytest.mark.parametrize("cell", CELLS)
@pytest.mark.parametrize("piece", PUZZLE.pieces, ids=lambda p: p.letter)
def test_candidate_matches_its_placement(
    piece: Piece, cell: tuple[int, int], all_rotations: bool
) -> None:
    row, col = cell
    cols = PUZZLE.cols
    found = CANDIDATES[all_rotations].at(row, col, piece.letter)
    assert found or cell != (3, 4)  # some corners have none, the middle cell always has some
    for candidate in found:
        placement = placements_of(piece, all_rotations)[candidate.placement_index]
        own = {(row + bit.row, col + bit.col) for bit in placement}
        assert candidate.mask == sum(1 << (r * cols + c) for r, c in own)
        assert [tuple(cell_tabs) for cell_tabs in candidate.cells] == [
            (
                (row + bit.row) * cols + col + bit.col,
                bit.north.value,
                bit.west.value,
                bit.south.value,
                bit.east.value,
            )
            for bit in placement
        ]
        expected: set[Check] = set()
        for bit in placement:
            for name, (dr, dc, facing) in SIDES.items():
                tab: Tab = getattr(bit, name)
                r, c = row + bit.row + dr, col + bit.col + dc
                on_board = 0 <= r < PUZZLE.rows and 0 <= c < cols
                if tab is not Tab.NONE and on_board and (r, c) not in own:
                    expected.add(Check(r * cols + c, facing, tab.value))
        assert len(candidate.checks) == len(expected)
        assert set(candidate.checks) == expected
