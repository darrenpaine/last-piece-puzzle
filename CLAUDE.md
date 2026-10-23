# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project
An algorithm to solve a series called "Last Piece Puzzle" created by Dugald
Keith in the 1990s and sold by Crystal Lines International.
The algorithm is converted to Python from a [C++ solution created by Anton](https://github.com/capnramses/golfing_madness_puzzle_solver)
for one of the puzzles ("Golfing Madness") and extended to cover the whole series.

## Stack
- Python 3.14, managed with `uv` (use `uv add` / `uv sync`, never bare pip)
- pytest (+ coverage), Ruff (lint + format), mypy (type check)
- GitHub Actions CI
- asyncio if needed, plus relevant pytest modules
- Models are stdlib dataclasses and `Enum` (no pydantic)

## Commands
Run these before saying a task is done.

| Task           | Command                                                    |
|----------------|------------------------------------------------------------|
| Install        | `uv sync`                                                  |
| Run (dev)      | `uv run last-piece-puzzle`                                 |
| Tests/Coverage | `uv run pytest --cov=src ./`                               |
| Fast tests     | `uv run pytest -m "not slow"`                              |
| One test       | `uv run pytest tests/path.py::test_name`                   |
| Lint           | `uv run ruff check .`                                      |
| Format         | `uv run ruff format .`                                     |
| Types          | `uv run mypy src/ tests/`                                  |
| C++ reference  | `g++ cpp/main.cpp -o build/hercules && echo \| ./build/hercules` |

CI runs lint, types, and tests on every push. Keep all three green. Check this locally using: `uv run pre-commit run --all-files`

## Instructions
- Follow the plan in @/PLAN.md
- Keep the original C++ untouched in @/cpp/main.cpp
- Python version and pytest never edit the recorded C++ solution fixture to make a test pass.
- Each PLAN step starts with a spec in `docs/specs/` (see SPEC-0001); I review it before code is written.

## Reference algorithm (`cpp/main.cpp`)
- 8×8 board. Each border has a fixed tab pattern (`Top/Left/Right/Bottom`). `Bottom[6]` and `Bottom[7]`
  are both `0`. This is deliberate: it breaks the alternating pattern, so the pieces fit only one way.
- 14 pieces, A–N, each made of 3–5 cells ("bits"), 64 cells in total. Each bit has an offset from the
  piece origin and a tab on each side (N/W/S/E).
- Tabs: `0` = inney, `1` = outey, `-1` = no tab (that side faces another bit of the same piece).
  Touching tabs must differ. A tab on the board edge fails if it equals that edge's value.
- Search: depth-first backtracking from the first empty cell in row-major order. For each unused piece
  it tries 4 rotations × each bit as the anchor, checking bounds, overlap, border tabs and neighbour tabs
  (`Sub1`/`Sub2`/`Sub3`).
- Rotation (clockwise): `(r, c) → (c, -r)`, and tabs move N←W, W←S, S←E, E←N.
- `InitPieces` adds each piece to the front of the list, so pieces are tried N→A. That order decides
  which solution is found first. `main()` never clears the board after a solution, so only the first is reported.

## Workflow: branches and pull requests
- Never commit directly to `main`. Start each feature or fix on a new branch from
  an up-to-date `main`: `git switch main && git pull && git switch -c <type>/<short-name>`
  (types: `feat/`, `fix/`, `docs/`, `chore/`; e.g. `feat/settings`).
- One branch per spec slice or concern. Keep the "small commits" rule within the branch.
- Before opening a PR, run `uv run pre-commit run --all-files` and the full test suite.
- Push with `git push -u origin <branch>` and open a PR to `main` with `gh pr create`.
  The PR description lists the spec ids it covers (e.g. SPEC-0001 B-0004, AT-0006).
  Do not add a "Generated with Claude Code" line or any other Claude attribution.
- Merge only after CI is green and I've approved. I merge; don't merge your own PR
  unless I ask. Delete the branch after merge.

## Layout
```
cpp/main.cpp                 # Anton's original solver (reference only, do not edit)
src/last_piece_puzzle/
  __init__.py                # main() entry point (`last-piece-puzzle` script)
  puzzles/                   # one module per puzzle definition, e.g. golfing_madness.py
docs/specs/                  # per-feature contract: goal, I/O, behavior, acceptance
tests/
  fixtures/                  # recorded solutions (do not edit to make tests pass)
PLAN.md                      # ordered work plan
```

## Conventions
- Type annotation hints everywhere - in src and tests; no untyped functions or parameters.
- Small commits with imperative messages, one concern each.
- Commit comments should be concise, simple language. Do not add 'co-author'.
- Ask me before adding dependencies.

## Non-goals (for now)
