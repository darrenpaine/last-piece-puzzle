"""Tabs, pieces and borders (SPEC-0003, SPEC-0005). Puzzle data lives in the puzzles package."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from enum import Enum
from functools import cached_property


class Tab(Enum):
    """Tab on one side of a bit, with the C++ encoding as its value."""

    IN = 0
    OUT = 1
    NONE = -1  # side faces another bit of the same piece


@dataclass(frozen=True)
class Bit:
    """One cell of a piece: its offset from the piece origin and its four tabs."""

    row: int
    col: int
    north: Tab
    west: Tab
    south: Tab
    east: Tab

    def rotated(self) -> Bit:
        """Turn 90 degrees clockwise about the piece origin (C++ RotatePiece)."""
        return Bit(
            self.col, -self.row, north=self.west, west=self.south, south=self.east, east=self.north
        )


# A piece's bits for one rotation, shifted so that the anchor bit is at (0, 0).
Placement = tuple[Bit, ...]


@dataclass(frozen=True)
class Piece:
    letter: str
    name: str
    bits: tuple[Bit, ...]

    @cached_property
    def placements(self) -> tuple[Placement, ...]:
        """Candidate placements in C++ order: each rotation, then each bit as the anchor."""
        placements: list[Placement] = []
        bits = self.bits
        for _ in range(4):
            for anchor in bits:
                placements.append(
                    tuple(replace(b, row=b.row - anchor.row, col=b.col - anchor.col) for b in bits)
                )
            bits = tuple(b.rotated() for b in bits)
        return tuple(placements)

    @cached_property
    def distinct_placements(self) -> tuple[Placement, ...]:
        """`placements` without rotations that repeat an earlier one, shape and tabs (SPEC-0007)."""
        count = len(self.bits)
        kept: list[Placement] = []
        seen: set[frozenset[tuple[int, int, Tab, Tab, Tab, Tab]]] = set()
        for k in range(4):
            rotation = self.placements[k * count : (k + 1) * count]
            top_row, top_col = min((b.row, b.col) for b in rotation[0])
            key = frozenset(
                (b.row - top_row, b.col - top_col, b.north, b.west, b.south, b.east)
                for b in rotation[0]
            )
            if key not in seen:
                seen.add(key)
                kept.extend(rotation)
        return tuple(kept)

    @cached_property
    def distinct_rotations(self) -> int:
        """1 if the piece is the same after 90 degrees, 2 if after 180 degrees, otherwise 4."""
        return len(self.distinct_placements) // len(self.bits)


class PieceSet:
    """The pieces of one puzzle, in definition order, with the C++ search order."""

    def __init__(self, pieces: Iterable[Piece]) -> None:
        self.pieces = tuple(pieces)
        self.by_letter = {p.letter: p for p in self.pieces}
        if len(self.by_letter) != len(self.pieces):
            raise ValueError("two pieces share a letter")
        # The C++ builds its piece list by pushing to the front, so it tries them in reverse.
        self.search_order = tuple(reversed(self.pieces))

    def __iter__(self) -> Iterator[Piece]:
        return iter(self.pieces)

    def __len__(self) -> int:
        return len(self.pieces)

    @property
    def cell_count(self) -> int:
        return sum(len(p.bits) for p in self.pieces)


@dataclass(frozen=True)
class Border:
    """Tab values of the board frame, one per row or column."""

    top: tuple[Tab, ...]
    left: tuple[Tab, ...]
    right: tuple[Tab, ...]
    bottom: tuple[Tab, ...]
