# SPEC-0003: Python port of the solver

Status: Draft

## Goal
A Python solver that follows the same search as `cpp/main.cpp` and finds the same first solution
(SPEC-0002). Pointers and mutable piece state are replaced with immutable data and object references.

## Inputs / Outputs
- `src/last_piece_puzzle/pieces.py`:
  - `Tab(Enum)`: `IN = 0`, `OUT = 1`, `NONE = -1` (C++ inney / outey / no tab).
  - frozen dataclass `Bit`: `row`, `col` offsets and `north`, `west`, `south`, `east` tabs.
  - frozen dataclass `Piece`: `letter`, `name` (the C++ printout name, e.g. "Bluehat"), `bits: tuple[Bit, ...]`.
  - `GOLFING_MADNESS_PIECES` (A–N, as in `ResetPiece`) and `GOLFING_MADNESS_BORDER`
    (`top`, `left`, `right`, `bottom`, as in `InitBoard`).
    This data moves to `puzzles/` in step 5 (SPEC-0006).
- `src/last_piece_puzzle/solver.py`:
  - `rotate(bit) -> Bit` and `orientations(piece)`: the candidate placements in C++ order.
  - `solve(pieces, border) -> SolveResult`, with `solution: Solution | None` (SPEC-0002 dataclass),
    `start_piece: str | None` and `moves: int`.
- `main()` (the `last-piece-puzzle` script) solves Golfing Madness. It prints the grid in the C++ layout,
  the move count, and the letter-to-name key.

## Behaviour
- B-0001: The piece and border data are the same as `cpp/main.cpp`: every bit's offset and tabs, and the four border arrays.
- B-0002: `rotate` turns a bit clockwise: `(r, c) → (c, -r)`, and the tabs move N←W, W←S, S←E, E←N.
- B-0003: Candidate order for one piece on one cell: for each rotation k = 0..3, for each anchor bit
  j in bit order, the offsets are `rotate^k(bits)` shifted so that bit j is at (0,0).
  This matches C++ `CheckFit`/`DisplacePiece`/`RotatePiece` without mutating the pieces.
- B-0004: A placement fits when every bit:
  - is on the board, on an empty cell;
  - has border tabs that are not equal to the border value (C++ `Sub2`);
  - has, on each side with a tab, a neighbouring placed bit whose facing tab is different (C++ `Sub3`).
- B-0005: The search is depth-first. Pieces are tried in the order N→A, starting at (0,0), then from
  the first empty cell in row-major order. Each place and each remove adds 1 to `moves`.
  The search stops at the first full board. As in C++, it does not continue to other solutions (that is step 6).
- B-0006: Board cells hold a reference to the placed bit (not a letter), so neighbour tabs are read
  directly. This replaces the C++ name lookup through the piece list.

## Acceptance tests
- AT-0001: The Python piece and border data equal the values parsed from `cpp/main.cpp`
  (`ResetPiece`, `InitPieces` `NumBits`, `InitBoard`) (B-0001).
- AT-0002: Rotating any bit 4 times gives the original bit. One rotation of a sample bit gives the expected offset and tabs (B-0002).
- AT-0003: `orientations` yields 4 × (number of bits) candidates, in rotation-then-anchor order, with the anchor bit at (0,0) (B-0003).
- AT-0004: Hand-built cases for `fits`: off the board, overlap, a border clash, a neighbour clash,
  and a valid placement (B-0004). Step 3 (SPEC-0004) adds more.
- AT-0005 (`slow`): `solve` on Golfing Madness returns the fixture grid, `start_piece == "E"` and
  `moves == 1529410`, the same as the C++ (B-0005, B-0006). An equal move count shows the search order is the same.
- AT-0006: `main()` prints the solved grid and the piece key. Tested with a stubbed `solve` so it stays fast.

## Out of scope
- Speed. The Python run time is measured and noted in the PR only (expected to be much slower than 1.2 s).
- A seeded start and rejection tests (step 3), the class refactor (step 4), all solutions (step 6).
