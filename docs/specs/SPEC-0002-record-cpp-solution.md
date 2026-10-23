# SPEC-0002: Record the C++ solution

Status: Reviewed

## Goal
Record the solution produced by the original C++ solver (`cpp/main.cpp`, v31) for the
"Golfing Madness" puzzle as a fixture. Later steps check the Python port against it.

## Observed C++ run
`g++ -O2 cpp/main.cpp` (g++ 15.2), stdin fed with newlines for the `getchar()` pauses:
- Pieces are tried at (0,0) in the order N→A. N, M, L, K, J, I, H, G and F fail, and E succeeds.
- `Move` counter at the solution: 1,529,410. It counts every place and remove since the start of the
  run, including the failed start pieces N–F.
- Run time: about 1.2 s.
- D, C, B and A are then tried on the already-full board, so they fail, and the run reports 1 solution.

```
E E E H J J J J
E H H H G N N J
K H G G G G N N
K K L L M M M N
K L L M M D D F
K C C C C D F F
A C I I D D B F
A A A I I I B B
```

## Inputs / Outputs
- Output: `tests/fixtures/golfing_madness_solution_1.txt`, a text file that is never edited by hand
  to make a test pass.
  - Lines starting with `#` are metadata, written as `# key: value`. The keys are `source`,
    `start_piece`, `moves` and `runtime`.
  - The 8 grid lines follow, each with 8 letters separated by single spaces, exactly as the C++ prints them.
- Code: `src/last_piece_puzzle/solution.py` with:
  - a frozen dataclass `Solution` with `grid: tuple[str, ...]` (8 strings of 8 letters) and
    `metadata: dict[str, str]`;
  - `load_solution(path: Path) -> Solution`.
  Step 6 reuses this to record every solution.

## Behaviour
- B-0001: The fixture holds the grid above and the metadata `source: cpp/main.cpp v31`,
  `start_piece: E`, `moves: 1529410`, `runtime: ~1.2s (g++ 15.2 -O2)`.
- B-0002: `load_solution` returns the grid rows without spaces, plus the metadata as a dict.
- B-0003: `load_solution` raises `ValueError` if the grid is not 8×8, or if a cell is not one of the letters A–N.
- B-0004: In the recorded grid, each letter covers exactly that piece's cell count
  (A4 B3 C5 D5 E4 F4 G5 H5 I5 J5 K5 L4 M5 N5, 64 in total) and its cells are 4-connected.
  The counts live in the test for now and move to the puzzle definition in step 5 (SPEC-0006).
- B-0005: A test compiles `cpp/main.cpp` into a temp dir and runs it with newlines on stdin. The grid
  and `Move` count it prints must equal the fixture. If `g++` is not installed the test is skipped.
  `cpp/main.cpp` is not changed.

## Acceptance tests
- AT-0001: Loading the fixture gives an 8×8 grid of letters A–N and the four metadata keys (B-0001, B-0002).
- AT-0002: A malformed file (a short row, a ninth row, an unknown letter) raises `ValueError` (B-0003).
- AT-0003: Every piece letter has the right cell count, and its cells are connected (B-0004).
- AT-0004: The output of the compiled C++ matches the fixture's grid and `moves` (B-0005).

## Out of scope
- Checking the tabs of the recorded solution. This needs the piece definitions, which come in steps 2–3.
- The other solutions. These come in step 6 (SPEC-0007).
