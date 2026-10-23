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

5. Puzzle definitions. The Golfing Madness pieces and border already moved to
   `src/last_piece_puzzle/puzzles/golfing_madness_puzzle.py` in step 2.
   What remains: a `Puzzle` definition (name, pieces, border) that the solver and CLI take as input,
   so the solver holds no puzzle-specific data and a new puzzle needs only a new module.
Spec: SPEC-0006.
Done when: all tests pass and the piece definitions are in the puzzles folder.

6. Find all solutions, not just the first.
   - Reset the board properly between start pieces, and keep searching after each solution is found.
   - Record every solution as a fixture (including the A and C start solutions).
   - D and H look the same after a 180° turn (tabs included), so the same board is found more than once:
     remove the duplicates.
Spec: SPEC-0007.
Done when: every start piece has been tried, and more than one solution is recorded (one for each of the 3–5 start pieces that work).

7. Investigate running the search in parallel, e.g. one start piece per worker, each with its own Board
   and pieces, using `multiprocessing` or the free-threaded build of Python 3.14.
Done when: it works and is shown to be faster than the step 6 baseline.

8. Investigate speed-ups. A GPU suits a branching backtracking search poorly, so try algorithm changes first:
   precompute every orientation of each piece, use bitboards, or treat it as an exact-cover problem (DLX)
   with extra tab checks. Try a GPU only if these are not enough.

9. Investigate generating a puzzle definition for another puzzle in the series from a photo. AI would
   identify the edges and pieces, and name each piece from the picture on it. This needs approval
   for new dependencies and for an LLM or vision service. Tests use a fake model, with no real calls.
