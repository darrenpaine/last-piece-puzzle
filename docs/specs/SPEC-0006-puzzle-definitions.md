# SPEC-0006: Puzzle definitions

Status: Draft (updated after PR review: CLI menu)

## Goal
The solver, board and CLI take a `Puzzle` as input and hold no puzzle-specific data, so adding a
puzzle from the series means adding one module to `src/last_piece_puzzle/puzzles/`.
Definitions are checked when they are loaded, so a mistake in the data (typed by hand or, later,
read from a photo in step 9) is caught before a long search.

## Inputs / Outputs
- `src/last_piece_puzzle/puzzle.py`: frozen dataclass `Puzzle(name: str, pieces: tuple[Piece, ...], border: Border)`.
  It is checked when created, and `piece_set` gives its `PieceSet`.
- Each puzzle module `puzzles/<key>_puzzle.py` defines `PUZZLE: Puzzle`.
  `golfing_madness_puzzle.py` defines `PUZZLE = Puzzle("Golfing Madness", ...)`, which replaces the
  `GOLFING_MADNESS_PIECES` / `GOLFING_MADNESS_BORDER` constants. The data is unchanged.
- `puzzles/__init__.py`:
  - `available() -> list[str]`: the keys of the puzzle modules found in the package, e.g. `["golfing_madness"]`;
  - `load(key) -> Puzzle`.
- API changes:
  - `Solver(puzzle)`, `solve(puzzle, start_pieces=None, on_start=None)`;
  - `check_solution(puzzle, grid)`, `Board.from_grid(puzzle, grid)`.
- CLI: `last-piece-puzzle [PUZZLE] [--list]`.
  - `PUZZLE` is a key, e.g. `golfing_madness`. With no `PUZZLE`, the CLI shows a numbered menu of the
    available puzzles and asks which one to solve, or `q` to exit.
  - `--list` prints the available keys with their names.
  - `main(argv: Sequence[str] | None = None)` so tests can call it.

## Behaviour
- B-0001: Creating a `Puzzle` raises `ValueError`, naming the piece or border, when:
  - two pieces share a letter;
  - `top` and `bottom` differ in length, or `left` and `right` do;
  - the total piece cells do not equal the board cells (rows × cols);
  - a piece has two bits on the same offset, or its bits are not connected;
  - a bit side is `NONE` but no bit of the same piece is next to it on that side, or the side has a tab
    but faces another bit of the same piece;
  - a border value is `NONE`.
- B-0002: `available()` finds the modules by name (`*_puzzle`) with `pkgutil`. `load` imports the module
  and returns its `PUZZLE`. An unknown key raises `ValueError` that lists the available keys.
- B-0003: The search is unchanged. The move counts stay 1,529,410 for the full run and 332,262 from E.
- B-0004: The CLI prints the puzzle's name in its header, then the same output as now.
  An unknown key exits with an argparse error (status 2) that lists the keys.
- B-0005: The menu (no `PUZZLE` given):
  - lists each puzzle as `1. Golfing Madness (golfing_madness)`, numbered from 1 in `available()` order;
  - prompts `Choose a puzzle (1-N, q to quit): `;
  - on a valid number, solves that puzzle;
  - on `q`, an empty line or end of input, exits with status 0 without solving;
  - on anything else, prints `Not a valid choice.` and asks again.

## Acceptance tests
- AT-0001: Each failure in B-0001 raises `ValueError` for a small hand-made puzzle. A valid small puzzle passes.
- AT-0002: The Golfing Madness `PUZZLE` is valid, named "Golfing Madness", with 14 pieces on an 8×8 board.
  The tests that compare the data with `cpp/main.cpp` use it.
- AT-0003: `available()` includes `golfing_madness`, and `load("golfing_madness")` is the same `PUZZLE`.
  `load("nope")` raises `ValueError` that mentions `golfing_madness` (B-0002).
- AT-0004: The existing tests pass with the new API, keeping their spec marks, including the move counts (B-0003).
- AT-0005: `main(["golfing_madness"])` prints the header and solution (with `solve` stubbed).
  `main(["--list"])` prints `golfing_madness: Golfing Madness`. `main(["nope"])` exits with status 2 (B-0004).
- AT-0006: With scripted input, `main([])` shows the numbered menu (B-0005):
  - `1` solves Golfing Madness;
  - `q`, an empty line and end of input each exit with status 0 without calling `solve`;
  - `x` then `1` prints `Not a valid choice.` once and then solves.

## Out of scope
- A data file format (JSON or similar). Puzzles stay as Python modules for now; step 9 can generate them.
- Other puzzles in the series. Their data is not available yet.
