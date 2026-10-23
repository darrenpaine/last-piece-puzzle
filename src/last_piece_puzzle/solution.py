"""Recorded puzzle solutions (SPEC-0002)."""

from dataclasses import dataclass, field
from pathlib import Path

GRID_SIZE = 8
PIECE_LETTERS = frozenset("ABCDEFGHIJKLMN")


@dataclass(frozen=True)
class Solution:
    """A solved board: one string of piece letters per row, plus `# key: value` metadata."""

    grid: tuple[str, ...]
    metadata: dict[str, str] = field(default_factory=dict)


def load_solution(path: Path) -> Solution:
    """Read a solution file; raise ValueError if the grid is not 8x8 letters A-N."""
    rows: list[str] = []
    metadata: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            key, _, value = line.removeprefix("#").partition(":")
            metadata[key.strip()] = value.strip()
        elif line.strip():
            cells = line.split()
            if len(cells) != GRID_SIZE:
                raise ValueError(f"row {len(rows)} has {len(cells)} cells, expected {GRID_SIZE}")
            bad = [cell for cell in cells if cell not in PIECE_LETTERS]
            if bad:
                raise ValueError(f"row {len(rows)} has unknown pieces {bad}")
            rows.append("".join(cells))
    if len(rows) != GRID_SIZE:
        raise ValueError(f"grid has {len(rows)} rows, expected {GRID_SIZE}")
    return Solution(grid=tuple(rows), metadata=metadata)
