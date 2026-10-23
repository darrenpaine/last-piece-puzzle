"""One module per puzzle in the series, named `<key>_puzzle.py` and defining `PUZZLE`."""

import importlib
import pkgutil

from last_piece_puzzle.puzzle import Puzzle

SUFFIX = "_puzzle"


def available() -> list[str]:
    """Keys of the puzzle modules in this package, e.g. `golfing_madness`."""
    return sorted(
        module.name.removesuffix(SUFFIX)
        for module in pkgutil.iter_modules(__path__)
        if module.name.endswith(SUFFIX)
    )


def load(key: str) -> Puzzle:
    keys = available()
    if key not in keys:
        raise ValueError(f"unknown puzzle {key!r}; available: {', '.join(keys)}")
    puzzle = importlib.import_module(f"{__name__}.{key}{SUFFIX}").PUZZLE
    if not isinstance(puzzle, Puzzle):
        raise TypeError(f"{key}{SUFFIX}.PUZZLE is not a Puzzle")
    return puzzle
