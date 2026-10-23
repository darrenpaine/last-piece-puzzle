# SPEC-0010: DLX exact cover algorithm

Status: Reviewed

## Goal
A second solver that treats the puzzle as an exact cover problem (Knuth's Algorithm X, "Dancing
Links" / DLX), with an extra rule for tabs. It finds the same solutions as the depth-first search (DFS)
much faster, and it becomes the CLI default (`--method dlx`). The DFS stays available as `--method search`,
with its exact move counts, C++ mode and workers.

## How it works
### 1. The puzzle as a table
An exact cover problem is a table of yes/no marks: choose rows so that every column is marked exactly once.
- **Columns:** one per board cell (64) and one per piece (14), 78 in all. A solution must fill every cell
  once and use every piece once.
- **Rows:** one per way a piece can sit on the board: each distinct rotation (`Piece.distinct_placements`)
  at each position that is on the board and passes the border tabs. A row marks the cells it covers and
  its own piece's column. For Golfing Madness there are 1,419 rows. For example, "E, rotation 0, top-left
  corner" marks cells (0,0), (0,1), (0,2) and (1,0), and the column "piece E".

Rows that cover each column exactly once make a board with no gaps, no overlaps and every piece used once.

### 2. Tabs
Exact cover knows nothing about tabs, so each row also has a list of **clashing rows**: placements that
would touch it on a shared edge with an equal tab (outey against outey, inney against inney). These are
worked out once, before the search. For Golfing Madness a row clashes with about 251 others on average.

### 3. The search
1. Pick the column with the fewest rows left: the hardest cell or piece to satisfy. If any column has
   no rows left, this branch is a dead end, so go back at once.
2. Try each remaining row of that column in turn. Choosing a row removes every row that shares a column
   with it (they would overlap it or reuse its piece), every row that clashes with it on tabs, and its own
   columns (now covered).
3. Repeat on what is left. When no columns are left, every cell and piece is covered and all tabs fit,
   so it is a solution.

DFS always fills the next empty cell in reading order. DLX works on whatever is most constrained, and it
removes impossible options as soon as they become impossible, so dead ends show up after one or two choices
instead of many placements later. For Golfing Madness it chooses about 19,500 rows, against about 715,000
placements for DFS.

### 4. Bitsets
Every set of rows is a Python int used as a bitset (bit `i` = row `i`):
- each column's rows;
- each row's "cannot go with me" rows (shared columns plus tab clashes), worked out once;
- the rows still possible, `alive`.

Choosing a row is then one operation, `alive & ~excludes[row]`, and counting a column's rows left is
`(rows[column] & alive).bit_count()`. Both run in C inside Python.

## Observed (prototypes in `build/`, Golfing Madness, single process)
| Solver                         | Time    | Steps                      |
|--------------------------------|---------|----------------------------|
| DFS now                        | 14.2 s  | 1,430,150 moves            |
| DFS fast engine (SPEC-0009)    | ~2.5 s  | 1,430,150 moves            |
| DLX, dict of sets              | 1.48 s  | 19,536 rows chosen         |
| DLX, bitsets                   | 0.067 s | 19,469 rows chosen         |
| DLX, bitsets, 10 process tasks | 0.28 s  | (process start-up is slower than the search) |

Both DLX versions found exactly the 5 fixture solutions, each once.

## Inputs / Outputs
- New module `src/last_piece_puzzle/dlx.py`. Its module docstring contains the "How it works" explanation above.
  - `CoverTable(puzzle)`: the rows (piece letter and placement per row), the column bitsets, and each
    row's `excludes` bitset.
  - `DlxSolver(Solver)`: overrides `solve(start_pieces=None, on_start=None, on_solution=None, workers=None)`
    and returns the usual `SolveResult`.
- `solve(puzzle, ..., method="search")` in `solver.py` gains `method`: `"search"` (the DFS, current
  behaviour) or `"dlx"`. The function's default stays `"search"`, so code and tests that need the exact move
  counts or the C++ comparison get them without asking.
- CLI: `--method {dlx,search}`, **default `dlx`**.
  - With `dlx`, the final line reads `5 solutions found in 19469 rows chosen, 0.1 s (DLX).`
    `--workers` and the progress lines for start pieces still work, but DLX runs in one process.
  - With `search`, the output is as now: `... moves, 2.5 s (16 workers).`
  - The default is switched to `dlx` in the last commit of this work, after the DLX tests pass.

## Behaviour
- B-0001: `DlxSolver` finds every distinct solution once. A placement reached from different anchors or
  rotations is one row, so there are no repeats: `times_found == 1`, and `boards_found` equals the number
  of solutions.
- B-0002: Solutions are returned, and passed to `on_solution`, in the same order as DFS. They are sorted
  by the path DFS would take to reach them: at each first free cell in reading order, the piece's
  search-order position and its placement index. `start_piece` is the piece covering (0, 0).
- B-0003: `SolveResult.moves` is the number of rows chosen, and `found_at_move` is the rows chosen so
  far when that solution was found. They are not comparable with DFS move counts.
- B-0004: `start_pieces` keeps only rows of those pieces among the rows covering cell (0, 0).
  `on_start` is called once for each allowed start piece, in search order, before the search.
- B-0005: `all_rotations` makes no difference (rows are distinct placements). `workers` is ignored, so DLX
  runs in one process.

## Acceptance tests
- AT-0001: For Golfing Madness, `solve(PUZZLE, method="dlx")` gives the 5 fixture grids in fixture order,
  start pieces E, E, C, C, A, `times_found == 1` and `boards_found == 5`. It runs in CI (well under 1 s)
  (B-0001, B-0002).
- AT-0002: With `start_pieces=["E"]`, it gives fixtures `_1` and `_2`. With `["M"]`, there are none (B-0004).
- AT-0003: For the small test puzzles (one cell, two solutions, no solution, symmetric domino), the DLX grids
  equal the DFS grids, in the same order (B-0001, B-0002).
- AT-0004: `CoverTable`: Golfing Madness has 1,419 rows. Each row marks its cells and its piece. A row's
  `excludes` contains every row that overlaps it or uses the same piece, plus the rows that clash on tabs,
  and not a row that sits next to it with fitting tabs. Checked on a hand-picked pair from fixture `_1`.
- AT-0005: With `solve` stubbed, `main(["golfing_madness"])` and `main(["golfing_madness", "--method", "dlx"])`
  pass `method="dlx"` and print the DLX final line. `main(["golfing_madness", "--method", "search"])` passes
  `method="search"` and prints the moves and workers line. An unknown method exits with status 2.
- AT-0006: `solve(PUZZLE)` with no `method` still uses the search: the existing move-count tests pass unchanged.

## Out of scope
- Running DLX in parallel (not needed at this speed).
