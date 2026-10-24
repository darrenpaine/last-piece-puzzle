## Plan

Each step from 1 to 6 starts with its spec in `docs/specs/`, which is reviewed before any code is written.
Steps 7 to 9 are investigations. They get a spec only if they lead to code that is kept.

0. Scaffolding. (Done)
   - Branch renamed from `master` to `main`, initial commit made (done).
   - After approval, add dev dependencies with `uv add --dev`: pytest, pytest-cov, ruff, mypy, pre-commit.
   - Add `.pre-commit-config.yaml` (ruff, ruff-format, mypy) and `.github/workflows/ci.yml` (lint, types, tests).
   - Register the pytest markers `spec` and `slow` in `pyproject.toml`.
   - Add `docs/specs/README.md` (spec index) and SPEC-0001 (spec and id conventions).
Done when: `uv run pre-commit run --all-files` and `uv run pytest` pass locally and in CI.

1. (Done) Check that the original C++ produces a solution, and record that solution as the first test fixture. This is the "Golfing Madness" puzzle.
   - Build it with `g++ cpp/main.cpp -o build/hercules` and run it. It waits on `getchar()` after a solution, so pipe in a newline.
   - Record the 8×8 letter grid in `tests/fixtures/golfing_madness_solution_1.txt`, along with the
     `Move` count and the run time. These give the cost baseline for the Python port.
   - Note: the C++ only ever reports the first solution. After a success, `main()` moves on to the next
     start piece without clearing the board, so every later attempt fails.
Spec: SPEC-0002.
Done when: the fixture is recorded and a test can load and check it (8×8, letters A–N, each piece's cell count matches).

2. (Done) Convert the C++ to Python. Replace pointers with object references.
   - Keep the search order. `InitPieces` adds each piece to the front of the list, so pieces are tried
     N→A. The first solution found depends on this order.
   - Use dataclasses and a tab `Enum` (`IN`/`OUT`/`NONE` for 0/1/-1) from the start.
Spec: SPEC-0003.
Done when: the code produces the same solution as the C++ code.

3. (Done) Check that the Python version produces the C++ solution.
   - Fast tests: the fit checker rejects wrong placements (a piece off the board, overlapping pieces,
     touching tabs that clash, a tab that clashes with the border, the wrong rotation).
   - Seeded test: start the search with the known start piece at (0,0) and check the result against the fixture.
   - `@slow` test: try every start piece. About 3–5 should lead to a solution, and the rest should fail.
Spec: SPEC-0004.
Done when: the fast tests and the seeded test pass in CI; the slow test passes locally.

4. (Done) Refactor into classes, e.g. Board, Piece, PieceSet (rotate, displace, fits, place, remove), and add unit tests for each.
Spec: SPEC-0005.
Done when: the unit tests pass and the solution is still produced.

5. (Done) Puzzle definitions. The Golfing Madness pieces and border already moved to
   `src/last_piece_puzzle/puzzles/golfing_madness_puzzle.py` in step 2.
   What remains: a `Puzzle` definition (name, pieces, border) that the solver and CLI take as input,
   so the solver holds no puzzle-specific data and a new puzzle needs only a new module.
Spec: SPEC-0006.
Done when: all tests pass and the piece definitions are in the puzzles folder.

6. (Done) Find all solutions by default, not just the first.
   - `solve` carries on after each full board and returns every distinct solution.
   - Pieces that look the same after a turn (shape and tabs, e.g. D and H after 180°) only try their
     distinct rotations, so each solution is found once. A C++ mode tries all 4 rotations for the C++ checks.
   - The CLI prints one line per solution found, then the key once, the numbered solutions, and the moves and time taken.
   - Record every solution as a fixture (including the A and C start solutions).
Spec: SPEC-0007.
Done when: all 5 Golfing Madness solutions are found, each once, and recorded as fixtures.

7. (Done) Investigate running the search in parallel, e.g. one start piece per worker, each with its own Board
   and pieces, using `multiprocessing` or the free-threaded build of Python 3.14.
Spec: SPEC-0008.
Done when: it works and is shown to be faster than the step 6 baseline.

8. (Done) Investigate speed-ups. A GPU suits a branching backtracking search poorly, so try algorithm changes first:
   precompute every orientation of each piece, use bitboards, or treat it as an exact-cover problem (DLX)
   with extra tab checks. Try a GPU only if these are not enough.
Spec: SPEC-0009.

9. (Done) Add a DLX exact cover solver and make it the CLI default (`--method dlx`). The depth-first
   searches stay as `--method fastsearch` and `--method search`, with their exact move counts and the
   C++ comparison.
Spec: SPEC-0010.
Done when: DLX finds the same 5 solutions in the same order, in well under a second.

10. Investigate generating a puzzle definition for another puzzle in the series from a photo. AI would
   identify the edges and pieces, and name each piece from the picture on it. This needs approval
   for new dependencies and for an LLM or vision service. Tests use a fake model, with no real calls.
