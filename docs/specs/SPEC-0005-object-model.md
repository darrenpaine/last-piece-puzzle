# SPEC-0005: Object model

Status: Draft

## Goal
Turn the free functions in `solver.py` into classes with clear jobs (Piece, PieceSet, Board, Solver)
without changing what the search does. The move counts stay exactly the same.

## Inputs / Outputs
- `pieces.py`:
  - `Bit.rotated() -> Bit`, which replaces `rotate(bit)`.
  - `Piece.placements: tuple[Placement, ...]`, which replaces `orientations(piece)`. It is computed once per piece.
  - New `PieceSet(pieces)`: the pieces of one puzzle, with `search_order` (N→A, the C++ order),
    `by_letter`, `__iter__` and `__len__`, plus `cell_count`.
  - `Tab`, `Border` and `Placement` (a type alias) are unchanged.
- New `board.py` with `Board(border)`:
  - `fits(placement, row, col)`: the C++ `Sub1`/`Sub2`/`Sub3` checks.
  - `place(letter, placement, row, col)` and `remove(placement, row, col)`.
  - `first_free() -> tuple[int, int] | None`, `is_full()`, `grid() -> tuple[str, ...]`, and `cell(row, col)`.
  - `Board.from_grid(pieces, border, grid) -> Board | None`, which replaces `build_board`.
- `solver.py`:
  - `Solver(pieces, border)` with `solve(start_pieces=None, on_start=None) -> SolveResult`.
  - The module functions `solve(...)` and `check_solution(...)` stay as thin wrappers, so `main()`
    and the callers keep the same signature.
- The Golfing Madness data module, `solution.py` and the CLI output are unchanged.

## Behaviour
- B-0001: `Bit.rotated` and `Piece.placements` give exactly what `rotate`/`orientations` gave (SPEC-0003 B-0002, B-0003).
- B-0002: `PieceSet` raises `ValueError` if two pieces share a letter. `search_order` is the reverse of the given order.
- B-0003: `Board` keeps the rules of SPEC-0003 B-0004 and B-0006. Each cell holds `(letter, Bit)` or None.
  `remove` undoes `place` exactly.
- B-0004: `Solver` searches in the same order as before, so the move counts stay the same:
  1,529,410 for the full run and 332,262 starting from E.
- B-0005: The full run takes no more than 25% longer than now (about 16 s). This is measured by hand and noted in the PR; it is not a test.

## Acceptance tests
- AT-0001: The existing SPEC-0002, SPEC-0003 and SPEC-0004 tests pass, rewritten for the new names and
  keeping their spec marks. This includes the move-count tests (B-0001, B-0003, B-0004).
- AT-0002: `Piece.placements` is computed once (the same object is returned each time) (B-0001).
- AT-0003: `PieceSet`: `search_order` is N→A, `by_letter` looks pieces up, `cell_count` is 64,
  and a duplicate letter raises `ValueError` (B-0002).
- AT-0004: `Board`: `place` then `remove` gives an empty board again; `first_free` moves along as cells fill and
  is None when full; `is_full`; `grid()` shows `.` for empty cells; `from_grid` rebuilds the fixture
  (B-0003).

## Out of scope
- A `Puzzle` definition type and a puzzle choice in the CLI (step 5, SPEC-0006).
- Finding all solutions (step 6) and speed work (steps 7–8).
