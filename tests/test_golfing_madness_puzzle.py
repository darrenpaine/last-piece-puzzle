import re
from pathlib import Path

import pytest

from last_piece_puzzle.pieces import Tab
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE

CPP_SOURCE = (Path(__file__).parent.parent / "cpp" / "main.cpp").read_text()


def cpp_function(name: str) -> str:
    """Body of a C++ function, skipping its forward declaration."""
    start = CPP_SOURCE.rindex(f"void {name}(")
    return CPP_SOURCE[start : CPP_SOURCE.index("\n}\n", start)]


def cpp_pieces() -> dict[str, list[tuple[int, ...]]]:
    """Each piece's bits as (row, col, north, west, south, east), read from ResetPiece."""
    pieces: dict[str, list[tuple[int, ...]]] = {}
    for block in cpp_function("ResetPiece").split("name == '")[1:]:
        values = {
            (field, int(i)): int(v)
            for field, i, v in re.findall(r"Ptr->(\w+)\[(\d)\] = (-?\d+);", block)
        }
        count = 1 + max(i for _, i in values)
        fields = ("RelRow", "RelCol", "NorthTabs", "WestTabs", "SouthTabs", "EastTabs")
        pieces[block[0]] = [tuple(values[(f, i)] for f in fields) for i in range(count)]
    return pieces


@pytest.mark.spec("SPEC-0003", "AT-0001")
def test_pieces_match_cpp() -> None:
    python = {
        p.letter: [
            (b.row, b.col, b.north.value, b.west.value, b.south.value, b.east.value) for b in p.bits
        ]
        for p in PUZZLE.pieces
    }
    assert python == cpp_pieces()


@pytest.mark.spec("SPEC-0003", "AT-0001")
def test_bit_counts_match_cpp_init_pieces() -> None:
    counts = re.findall(r"Name = '([A-N])';\s*Ptr->NumBits = (\d+);", cpp_function("InitPieces"))
    assert {p.letter: len(p.bits) for p in PUZZLE.pieces} == {
        letter: int(n) for letter, n in counts
    }


@pytest.mark.spec("SPEC-0003", "AT-0001")
@pytest.mark.parametrize("side", ["top", "left", "right", "bottom"])
def test_border_matches_cpp(side: str) -> None:
    cpp = re.findall(rf"{side.capitalize()}\[\d\] = (\d);", cpp_function("InitBoard"))
    assert getattr(PUZZLE.border, side) == tuple(Tab(int(v)) for v in cpp)
