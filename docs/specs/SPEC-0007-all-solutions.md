# SPEC-0007: Find all solutions

Status: Draft (rewritten after PR review)

## Goal
`solve` searches the whole tree by default and returns every distinct solution. Rotations that
give the same piece placement (a piece that looks the same after a turn, shape and tabs included) are
tried only once, so other puzzles get the same benefit. A C++ mode keeps the exact C++ search for the
regression checks.

## Changes to earlier specs
- SPEC-0003 B-0005 and SPEC-0004 B-0001: `solve` no longer stops at the first full board, and by
  default it skips repeated rotations. The C++ move counts now come from C++ mode (`all_rotations=True`),
  as the move at which the first solution is found.
- SPEC-0003 B-0003: `Piece.placements` is unchanged (all 4 rotations, C++ order). The new
  `Piece.distinct_placements` is what the default search uses.
- The CLI output of SPEC-0003 AT-0006 and SPEC-0006 B-0004 changes as described below.

## Observed (prototype, Golfing Madness)
| Mode                 | Start | Solutions | Boards | Moves     | Time   |
|----------------------|-------|-----------|--------|-----------|--------|
| default              | all   | 5         | 5      | 1,430,150 | 14.2 s |
| default              | E     | 2         | 2      | 335,338   | 3.4 s  |
| default              | A     | 1         | 1      | 66,078    | 0.7 s  |
| C++ (`all_rotations`)| all   | 5         | 20     | 2,654,638 | 28.6 s |
| C++ (`all_rotations`)| E     | 2         | 8      | 645,422   | 7.0 s  |
| C++ (`all_rotations`)| A     | 1         | 4      | 106,660   | 1.2 s  |

Distinct rotations per piece: D and H have 2, and every other piece has 4.

| # | Start | First found: default | First found: C++ mode | Row 0      |
|---|-------|----------------------|-----------------------|------------|
| 1 | E     | 882,594              | 1,529,410             | `EEEHJJJJ` |
| 2 | E     | 899,460              | 1,551,402             | `EEEHIAAA` |
| 3 | C     | 1,281,818            | 2,387,466             | `CCCCJJJJ` |
| 4 | C     | 1,320,874            | 2,462,612             | `CCCCEEEK` |
| 5 | A     | 1,377,280            | 2,570,948             | `AKKKKNNF` |

## Inputs / Outputs
- `pieces.py`:
  - `Piece.distinct_rotations: int` (1, 2 or 4);
  - `Piece.distinct_placements`: like `placements`, but leaving out every rotation whose cells and tabs
    (ignoring position) equal an earlier rotation's.
- `solver.py`:
  - frozen dataclass `FoundSolution`: `solution: Solution`, `start_piece: str`, `found_at_move: int`,
    `times_found: int`.
  - `SolveResult` becomes: `solutions: tuple[FoundSolution, ...]` (in the order first found),
    `boards_found: int` (counting repeats) and `moves: int`.
  - `Solver(puzzle, all_rotations=False)`.
  - `solve(puzzle, start_pieces=None, on_start=None, on_solution=None, all_rotations=False)`.
    `on_solution` is called with each new `FoundSolution`, numbered from 1.
- `solution.py`: `format_solution(solution) -> str` and `save_solution(path, solution)`, writing the
  SPEC-0002 file format, so `load_solution` reads them back unchanged.
- Fixtures `tests/fixtures/golfing_madness_solution_2.txt` to `_5.txt`: solutions 2–5, written with
  `save_solution`. Metadata: `source: python solve`, `start_piece`, `found_at_move` (default mode).
  `_1.txt` (the C++ fixture) is not changed.
- CLI output (no flag needed):
  ```
  Last Piece Puzzle solver: Golfing Madness
  Trying to start puzzle with piece N...
  ...
  Solution 1 found starting with piece E at move 882594
  ...
  Key:
  A = Bluehat
  ...

  Solution 1 (start piece E):
  E E E H J J J J
  ...

  5 solutions found in 1430150 moves, 14.2 s.
  ```
  With none found, the key and list are skipped and the last line is `No solutions found in N moves, T s.`

## Behaviour
- B-0001: After a full board, `solve` records it and then backtracks as if it had failed, so the search
  carries on. The order and move counting are otherwise the same as before.
- B-0002: `distinct_placements` keeps a rotation only if its set of (offset from its top-left bit, tabs)
  differs from every earlier rotation's. The kept rotations stay in C++ order, each with all its anchor
  bits. A piece that is the same after 90° keeps 1 rotation, after 180° keeps 2, otherwise 4.
- B-0003: By default the search uses `distinct_placements`; with `all_rotations=True` it uses `placements`
  (C++ mode).
- B-0004: A board whose letter grid equals one already found is a repeat. It increases `times_found` and
  `boards_found` but is not a new solution. In C++ mode each Golfing Madness solution is found 4 times;
  in the default mode, once.
- B-0005: `start_pieces` and `on_start` work as before.
- B-0006: The CLI shows the progress lines, one line per new solution, then the key once, the numbered
  solution grids, and a final line with the solution count, total moves and time taken (1 decimal place).

## Acceptance tests
- AT-0001: `distinct_rotations` is 2 for D and H and 4 for the other Golfing Madness pieces. A
  plus-shaped test piece with the same tab on every outside side gives 1, and a 2×1 piece gives 2 or 4
  depending on its tabs (B-0002).
- AT-0002: On a small puzzle with a 180°-symmetric piece, the default mode finds each solution once, and C++ mode
  finds it twice with `times_found == 2` (B-0003, B-0004).
- AT-0003: `save_solution` then `load_solution` gives the same grid and metadata.
- AT-0004: Fixtures `_2` to `_5` load, pass `check_solution`, and are all different from each other and from `_1`.
- AT-0005 (CI, about 3.4 s): `solve(PUZZLE, start_pieces=["E"])` finds fixtures `_1` and `_2` in that
  order, each once, in 335,338 moves.
- AT-0006 (CI, about 1.2 s): C++ mode with `start_pieces=["A"]` finds fixture `_5`, first at move 22,970
  (the same as the SPEC-0004 observed C++-order count), with `times_found == 4`.
- AT-0007 (`slow`, about 14 s): the default `solve(PUZZLE)` gives the 5 fixtures in table order, with start
  pieces E, E, C, C, A, the default first-found moves, and `moves == 1430150`.
- AT-0008 (`slow`, about 29 s): C++ mode `solve(PUZZLE)` finds solution 1 at move 1,529,410 (the C++ fixture
  `moves`), with 5 solutions, `boards_found == 20`, and `moves == 2654638`.
- AT-0009: `main(["golfing_madness"])`, with `solve` stubbed to return 2 solutions, prints the found lines,
  the key once, the two numbered grids and the final line. With 0 solutions it prints only the
  no-solutions line.

## Out of scope
- Other speed-ups and parallel search (steps 7–8).
