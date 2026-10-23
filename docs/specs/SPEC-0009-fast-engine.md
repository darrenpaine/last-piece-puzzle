# SPEC-0009: Fast search engine

Status: Reviewed

## Goal
Make each search several times faster without changing what it finds or how it counts. The same
placements are tried in the same order, so every move count in the earlier specs stays exactly the same.

## Observed
### Prototypes, Golfing Madness, single process (current search: 14.2 s default, 28.6 s C++ mode)
| Prototype                                                       | Default | C++ mode | Moves      |
|-----------------------------------------------------------------|---------|----------|------------|
| Placements checked ahead of time per cell, bitmask, int tabs    | 4.7 s   | 4.9 s    | identical  |
| Same, with the hot loop on local and closure variables          | 2.5 s   | –        | identical  |
| Same, plus pruning empty pockets smaller than the smallest piece | 2.5 s   | –        | 1,084,280 (−24%) |

- Checking which placements are on the board and clear of the border at each cell takes about 0.05 s,
  once per solve. At run time only overlap (one AND on a 64-bit mask) and neighbour tabs (small ints)
  are left to check.
- Pruning cuts moves but saves no time, and it changes the move counts. **Not adopted.**

### With workers (one task per start piece, 14 workers, prototype engine)
| Build              | Threads | Processes |
|--------------------|---------|-----------|
| standard           | 2.6 s   | 1.0 s     |
| free-threaded 3.14t | 1.3 s   | 1.1 s     |

With plain ints (small ints are never reference-counted in 3.14), threads now scale on the free-threaded
build, but processes are still a little faster and work on the standard build. **Processes stay.**

### Not tried
- **Exact cover (DLX):** tried afterwards in `build/` (about 0.07 s single process with bitsets). It searches in
  a different order, so the move counts and the C++ comparison do not hold. It is specified separately as
  an alternative solver in SPEC-0010; this spec keeps the depth-first search.
- **GPU:** a branching backtracking search with few, small, uneven subtrees suits a GPU poorly, and it
  would need a new dependency (e.g. CUDA via CuPy or Numba). With about 0.5 s expected on CPU workers,
  there is little to gain.

## Inputs / Outputs
- New module `src/last_piece_puzzle/engine.py`:
  - `Candidates(puzzle, all_rotations)`, built once per solve. For each board cell and each piece (in
    search order), it lists that piece's placements (same order as `placements` / `distinct_placements`)
    anchored at the cell that are on the board and pass the border tabs. Each candidate holds:
    - the occupancy bitmask;
    - each covered cell with its 4 tabs as ints;
    - the neighbour checks: neighbour cell, which of its sides faces this bit, and this bit's tab value;
    - the placement index.
  - `Engine`: the search, using a 64-bit occupancy int and tab arrays of ints. It keeps the moves, the
    full-board count and the solutions found, with the same counting as `Solver` (SPEC-0007 B-0001).
- `Solver` keeps its public API (`Solver(puzzle, all_rotations)`, `solve(...)`, `reset`) and runs the
  search with `Engine`. `parallel.py` workers run their tasks with `Engine`, starting each task from its
  prefix path.
- `Board`, `Piece.placements` etc. stay as they are; `Board.from_grid` and `check_solution` still use them.

## Behaviour
- B-0001: For any puzzle, start pieces and mode, `Engine` tries the same fitting placements in the same
  order as the current `Solver`. So `solutions`, `found_at_move`, `times_found`, `boards_found` and `moves`
  are unchanged, with and without workers.
- B-0002: A candidate is left out of a cell's list only if it is off the board or clashes with the border
  there, which can never fit. Overlap and neighbour tabs are checked at run time.
- B-0003: The single-process full search (default mode) is at least 3× faster than before (14.2 s →
  about 5 s or less). This is measured and noted in the PR, not tested.

## Acceptance tests
- AT-0001: All existing tests pass unchanged, including every exact move count (B-0001).
- AT-0002: For each Golfing Madness piece, the candidates at a cell equal the placements for which
  `Board(border).fits(placement, row, col)` is true on an empty board, in the same order. Checked at
  (0, 0), at a middle cell and at the bottom-right corner (B-0002).
- AT-0003: A candidate's mask, cell tabs and neighbour checks match its placement: the cell bits equal
  the placement's cells, and the checks cover exactly the bit sides that have a tab and face an on-board
  cell outside the piece (B-0002).

## Out of scope
- Pruning, DLX and GPU (above).
- A thread option for the free-threaded build.
