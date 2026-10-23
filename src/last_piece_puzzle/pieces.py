"""Tabs, pieces and borders (SPEC-0003). Puzzle data lives in the puzzles package."""

from dataclasses import dataclass
from enum import Enum


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


@dataclass(frozen=True)
class Piece:
    letter: str
    name: str
    bits: tuple[Bit, ...]


@dataclass(frozen=True)
class Border:
    """Tab values of the board frame, one per row or column."""

    top: tuple[Tab, ...]
    left: tuple[Tab, ...]
    right: tuple[Tab, ...]
    bottom: tuple[Tab, ...]
