# SPEC-0004: Solution and fit tests

Status: Draft

## Goal
Show that the Python solver produces the C++ solution quickly, that it rejects wrong placements,
and which start pieces lead to a solution.

## Observed (Python, fresh board per start piece, first solution only)
| Start | Solves | Moves   | Time  |
|-------|--------|---------|-------|
| N     | no     | 239,580 | 2.4 s |
| M     | no     | 0       | 0.0 s |
| L     | no     | 231,328 | 2.5 s |
| K     | no     | 313,268 | 3.2 s |
| J     | no     | 139,144 | 1.4 s |
| I     | no     | 181,824 | 2.0 s |
| H     | no     | 0       | 0.0 s |
| G     | no     | 92,004  | 0.9 s |
| F     | no     | 0       | 0.0 s |
| E     | yes    | 332,262 | 3.5 s |
| D     | no     | 172,704 | 1.7 s |
| C     | yes    | 372,192 | 3.5 s |
| B     | no     | 12,794  | 0.2 s |
| A     | yes    | 22,970  | 0.2 s |

The moves for N to F plus E add up to 1,529,410, the C++ total. M, H and F cannot sit in the corner at all.

## Inputs / Outputs
- `solve(pieces, border, start_pieces: Sequence[str] | None = None, on_start=None)`:
  `start_pieces` limits which pieces are tried at (0,0). They are still tried in C++ order (N→A).
  `None` means all of them, as before. Each start piece begins on a fresh board.
- `check_solution(pieces, border, grid: Sequence[str]) -> bool` in `solver.py`: True if the letter grid
  can be built from the pieces with every tab fitting. Step 6 reuses it to check recorded solutions.

## Behaviour
- B-0001: `start_pieces` only filters the start pieces. The search inside each start is unchanged,
  and `moves` counts only the starts that were tried.
- B-0002: `check_solution`:
  - each letter's cells must equal some rotation of that piece (a placement from `orientations`);
  - placing the pieces in order of first appearance (row-major), each must pass `fits` for one of its
    matching placements, trying the others if needed (backtracking);
  - it returns False if a letter is unknown or missing, the shape is wrong, or no tabs fit.
- B-0003: Exactly A, C and E lead to a solution as the piece at (0,0). Every other start piece fails.

## Acceptance tests
- AT-0001: `solve(..., start_pieces=["E"])` returns the fixture grid with `start_piece == "E"` and
  `moves == 332262`. It takes about 3.5 s and runs in CI (B-0001).
- AT-0002: `check_solution` accepts the fixture grid (B-0002).
- AT-0003: `check_solution` rejects (B-0002):
  - the fixture rotated 180°, and the fixture mirrored. The border pattern, including the deliberate
    `Bottom[6]`/`Bottom[7]` break, means these do not fit;
  - two pieces of the same size swapped;
  - an unknown letter, or a piece missing;
  - a grid where one piece's cells are not its shape.
- AT-0004: On the solved fixture board with one piece removed, `fits` accepts that piece's correct
  placement and rejects every other placement of it over the gap (a wrong rotation). Checked for every piece (B-0002).
- AT-0005 (`slow`, about 25 s): trying each start piece on its own gives a solution for exactly
  {A, C, E}. Each solution found passes `check_solution` (B-0003).

## Out of scope
- More than one solution per start piece, and recording the A and C solutions as fixtures (step 6, SPEC-0007).
