# SPEC-0007: Find all solutions

Status: Draft

## Goal
Search the whole tree instead of stopping at the first full board. Report each distinct solution once
and record them all as fixtures.

## Observed (prototype exhaustive search on Golfing Madness, C++ order)
- 20 full boards in total, but only **5 distinct grids**. Each grid is found 4 times, because D and H
  are both the same after a 180° turn, tabs included (SPEC-0004), giving 2 × 2 identical placements.
- Distinct solutions by start piece: E 2, C 2, A 1.
- Total moves for the whole search: 2,654,638. Time: about 29 s.
- The first solution found is the C++ fixture, at move 1,529,410.

| # | Start | First found at move | Row 0      |
|---|-------|---------------------|------------|
| 1 | E     | 1,529,410           | `EEEHJJJJ` |
| 2 | E     | 1,551,402           | `EEEHIAAA` |
| 3 | C     | 2,387,466           | `CCCCJJJJ` |
| 4 | C     | 2,462,612           | `CCCCEEEK` |
| 5 | A     | 2,570,948           | `AKKKKNNF` |

## Inputs / Outputs
- `solver.py`:
  - frozen dataclass `FoundSolution`: `solution: Solution`, `start_piece: str`, `found_at_move: int`, and
    `times_found: int` (4 for each Golfing Madness solution);
  - frozen dataclass `AllResult`: `solutions: tuple[FoundSolution, ...]` in the order they were first found,
    `boards_found: int` (counting duplicates) and `moves: int`;
  - `Solver.solve_all(start_pieces=None, on_start=None, on_solution=None) -> AllResult` and a module
    wrapper `solve_all(puzzle, ...)`. `on_solution` is called with each new distinct `FoundSolution`.
- `solution.py`: `format_solution(solution) -> str` and `save_solution(path, solution)`, writing the
  SPEC-0002 file format (metadata lines, then the grid). `load_solution` reads them back unchanged.
- Fixtures `tests/fixtures/golfing_madness_solution_2.txt` to `_5.txt` for solutions 2–5 above.
  Metadata: `source: python solve_all`, `start_piece`, `found_at_move`. They are written with `save_solution`.
  `_1.txt` (the C++ fixture) is not changed.
- CLI: `last-piece-puzzle [PUZZLE] --all` prints each distinct solution as it is found
  (`Solution N FOUND starting with piece X at move M`, then the grid), then
  `Total Solutions Found = 5 (20 boards including duplicates) in 2654638 Moves.`
  Without `--all` the output is unchanged.

## Behaviour
- B-0001: `solve_all` uses the same search order and move counting as `solve`, but after a full board it
  records the board and then backtracks as if it had failed, so it carries on. The move count up to the
  first solution therefore matches `solve`.
- B-0002: Two boards are the same solution if their letter grids are equal. Identical placements give
  identical tabs, so equal grids are physically the same. The first time a grid is found it is recorded;
  each repeat only increases `times_found` and `boards_found`.
- B-0003: `start_pieces` and `on_start` behave as in `solve`. Each start piece begins on an empty board.
- B-0004: `solve` is unchanged (first solution only, same move counts).

## Acceptance tests
- AT-0001: On a small puzzle with a piece that is the same after a 180° turn, `solve_all` returns each
  distinct grid once, with the right `times_found`, `boards_found` and `moves` (B-0001, B-0002).
- AT-0002: `save_solution` then `load_solution` gives the same grid and metadata (round trip).
- AT-0003: The fixtures `_2` to `_5` load, pass `check_solution`, and are all different from each other and from `_1`.
- AT-0004: `solve_all(PUZZLE, start_pieces=["A"])` finds exactly the fixture `_5` grid, 4 times.
  This runs in CI if it takes under 5 s; otherwise it is marked `slow`.
- AT-0005 (`slow`, about 30 s): `solve_all(PUZZLE)` gives:
  - 5 solutions in the table order, with grids equal to fixtures `_1`–`_5`;
  - start pieces E, E, C, C, A, and first-found moves as in the table;
  - `times_found == 4` each, `boards_found == 20`, `moves == 2654638`.
- AT-0006: `main(["golfing_madness", "--all"])` (with `solve_all` stubbed) prints each solution and the total line.

## Out of scope
- Skipping repeated placements of symmetric pieces during the search. It would make the search about 4×
  faster here, but it changes the move counts compared with the C++. It is a step 8 speed-up.
- Parallel search (step 7).
