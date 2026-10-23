# SPEC-0008: Parallel search

Status: Draft

## Goal
Run the search on several CPU cores at once, so a full solve takes a fraction of the step 6 time, while
giving exactly the same result as the single-process search.

## Observed (prototype, Golfing Madness, default mode, 22-core machine, `ProcessPoolExecutor`)
Single process: 1,430,150 moves, about 14.2 s.

| Split                                  | Tasks | 8 workers | 16 workers | 22 workers |
|----------------------------------------|-------|-----------|------------|------------|
| one task per start piece               | 14    | –         | 5.1 s      | 5.0 s      |
| start piece + first placement          | 15    | –         | 4.2 s      | 4.1 s      |
| first placements, ≥ 100 tasks          | 114   | 4.5 s     | 3.1 s      | 3.2 s      |
| first placements, ≥ 400 tasks          | 1,101 | 3.8 s     | 2.3 s      | 2.5 s      |
| first placements, ≥ 1,500 tasks        | 4,408 | 3.5 s     | 2.1 s      | 2.2 s      |

Splitting by start piece alone is limited by the E and C branches (about 4–5 s each). Splitting a few
placements deep gives many small tasks and balances well, at about 6.7× faster. More than 16 workers
does not help on this machine.

### Free-threaded Python (3.14.8t, GIL off), same 4,408 tasks
| Run                                   | 1     | 4 workers | 8 workers | 16 workers | 22 workers |
|---------------------------------------|-------|-----------|-----------|------------|------------|
| standard build, threads               | 14.2 s| 14.6 s    | 14.6 s    | 14.5 s     | 14.6 s     |
| standard build, processes             |       | 6.0 s     | 3.6 s     | 2.0 s      | 2.2 s      |
| free-threaded, threads                | 15.0 s| 13.0 s    | 14.3 s    | 21.3 s     | 24.1 s     |
| free-threaded, threads, puzzle copied per thread |  | 11.9 s | 15.0 s | 21.0 s |       |
| free-threaded, processes              |       | 6.2 s     | 3.9 s     | 2.4 s      | 2.4 s      |

On the free-threaded build, threads barely help, and they get slower above 4. A likely cause is the
threads contending to update reference counts on shared objects (`Tab` members, bits, tuples). Copying the
puzzle per thread does not fix it, because enum members and classes are still shared. Making threads scale would need the data
stored as plain ints or bitboards (step 8). For now processes are the fastest on both builds, so this
spec uses processes. Threads can be tried again after step 8.

## Inputs / Outputs
- `solve(puzzle, ..., workers: int | None = None)`:
  - `None` or `1` runs the current single-process search;
  - `workers > 1` runs it with that many worker processes.
  The return value and callbacks are the same in both cases.
- New module `src/last_piece_puzzle/parallel.py` holds the split and the merge. `solver.py` calls it when
  `workers > 1`.
- CLI: `last-piece-puzzle [PUZZLE] [--workers N]`. The default is the number of CPUs available
  (`os.process_cpu_count()`), and `--workers 1` uses a single process. The final line names the worker
  count: `5 solutions found in 1430150 moves, 2.1 s (16 workers).`

## Behaviour
- B-0001: Split. Starting from the empty board, the search tree is expanded placement by placement in the
  normal search order (start pieces filtered by `start_pieces`) to the smallest depth that gives at least
  `100 × workers` tasks, or until no node can grow. A task is the list of placements from the empty board
  to one node at that depth (each placed at the first free cell). A node that is a full board is a task too.
- B-0002: Each worker process builds the puzzle's `Solver` once, at start-up. For each task it places the
  prefix and searches the rest of that subtree with the normal search, returning its local move count and
  the solutions found, each with its local move number.
- B-0003: Merge. The tasks are listed in the order the single-process search would reach them.
  `ProcessPoolExecutor.map` returns results in that order. The parent keeps a running move count: each
  prefix node above the tasks adds 1 when placed and 1 when removed, and each task adds its own moves.
  So every `found_at_move`, the solution order and numbering, `times_found`, `boards_found` and `moves`
  equal the single-process result.
- B-0004: Callbacks. `on_start(letter)` is called when the first result for a new start piece is
  merged, and `on_solution` when a new solution is merged, in the same order as the single-process search.
  They come in bursts as results arrive, not live.
- B-0005: `all_rotations` works in parallel too.
- B-0006: Worker errors are raised in the parent, not swallowed.

## Acceptance tests
- AT-0001: For the small test puzzles (1×1, 1×2 with no solution, 1×2 with two solutions, the symmetric
  domino in both modes), `solve(..., workers=2)` equals `solve(...)`, including the callbacks' order and
  arguments (B-0001, B-0003, B-0004, B-0005).
- AT-0002: For Golfing Madness, the split for `start_pieces=["E"]` and 2 workers gives at least 200
  tasks in single-process order. Placing each task's prefix from an empty board never fails (B-0001).
- AT-0003 (CI): `solve(PUZZLE, start_pieces=["E"], workers=2)` gives the SPEC-0007 AT-0005 values:
  fixtures `_1` and `_2`, found at 201,634 and 218,500, with 335,338 moves (B-0003).
- AT-0004 (`slow`): `solve(PUZZLE, workers=4)` gives the SPEC-0007 AT-0007 values (5 fixtures, first-found
  moves, 1,430,150 moves), and in C++ mode the AT-0008 values (1,529,410 for the first solution, 20 boards,
  2,654,638 moves).
- AT-0005 (`slow`, skipped below 4 CPUs): a full solve with 4 workers is at least 2× faster than with 1.
- AT-0006: `main(["golfing_madness", "--workers", "3"])` passes `workers=3` to `solve` (stubbed) and
  prints `(3 workers)` in the final line. Without `--workers`, it passes `os.process_cpu_count()`.

## Out of scope
- A thread-based option for the free-threaded build. Measured above, it is slower than processes for now;
  try it again after step 8. The free-threaded Python is installed locally with `uv python install 3.14t`,
  but the project and CI stay on the standard build.
- Making each task faster (step 8).
