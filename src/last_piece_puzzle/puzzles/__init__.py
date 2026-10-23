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
    """Import a puzzle module and return its PUZZLE; any failure raises ValueError (SPEC-0006)."""
    keys = available()
    if key not in keys:
        raise ValueError(f"unknown puzzle {key!r}; available: {', '.join(keys)}")
    module_name = f"{__name__}.{key}{SUFFIX}"
    try:
        # A module that fails to import, or whose Puzzle fails its checks, raises here.
        puzzle = importlib.import_module(module_name).PUZZLE
    except (ImportError, SyntaxError, AttributeError, ValueError) as error:
        raise ValueError(f"puzzle {key!r} cannot be loaded: {error}") from error
    if not isinstance(puzzle, Puzzle):
        raise ValueError(f"puzzle {key!r} cannot be loaded: PUZZLE is not a Puzzle")
    return puzzle
