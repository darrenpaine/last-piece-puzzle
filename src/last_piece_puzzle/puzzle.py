"""A puzzle definition: its pieces and border, checked when created (SPEC-0006)."""

from dataclasses import dataclass
from functools import cached_property

from last_piece_puzzle.pieces import Border, Piece, PieceSet, Tab

# Each side of a bit: the tab attribute and the offset of the cell it faces.
SIDES = (("north", -1, 0), ("south", 1, 0), ("west", 0, -1), ("east", 0, 1))


@dataclass(frozen=True)
class Puzzle:
    name: str
    pieces: tuple[Piece, ...]
    border: Border

    def __post_init__(self) -> None:
        border = self.border
        if len(border.top) != len(border.bottom) or len(border.left) != len(border.right):
            raise ValueError(f"{self.name}: border top/bottom or left/right lengths differ")
        sides = (border.top, border.left, border.right, border.bottom)
        if any(tab is Tab.NONE for side in sides for tab in side):
            raise ValueError(f"{self.name}: border has a NONE value")
        cells = self.piece_set.cell_count  # PieceSet rejects duplicate letters
        if cells != self.rows * self.cols:
            raise ValueError(
                f"{self.name}: pieces cover {cells} cells, board has {self.rows * self.cols}"
            )
        for piece in self.pieces:
            _check_piece(piece)

    @cached_property
    def piece_set(self) -> PieceSet:
        return PieceSet(self.pieces)

    @property
    def rows(self) -> int:
        return len(self.border.left)

    @property
    def cols(self) -> int:
        return len(self.border.top)


def _check_piece(piece: Piece) -> None:
    """Check that the bits do not overlap, are connected, and have tabs only on outside sides."""
    bits = {(b.row, b.col): b for b in piece.bits}
    if len(bits) != len(piece.bits):
        raise ValueError(f"piece {piece.letter}: two bits share an offset")
    start = next(iter(bits))
    seen = {start}
    todo = [start]
    while todo:
        r, c = todo.pop()
        for _, dr, dc in SIDES:
            step = (r + dr, c + dc)
            if step in bits and step not in seen:
                seen.add(step)
                todo.append(step)
    if seen != bits.keys():
        raise ValueError(f"piece {piece.letter}: bits are not connected")
    for (r, c), bit in bits.items():
        for side, dr, dc in SIDES:
            own = (r + dr, c + dc) in bits
            tab = getattr(bit, side)
            if own and tab is not Tab.NONE:
                raise ValueError(
                    f"piece {piece.letter}: bit {r},{c} has a {side} tab facing itself"
                )
            if not own and tab is Tab.NONE:
                raise ValueError(f"piece {piece.letter}: bit {r},{c} has no {side} tab")
