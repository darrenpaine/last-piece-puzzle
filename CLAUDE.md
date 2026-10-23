# CLAUDE.md

## Project
An algorithm to solve a series called "Last Piece Puzzle" created by Dugald
Keith in the 1990s and sold by Crystal Lines International.
The algorithm is coverted to Python from a [C++ solution created by Anton](https://github.com/capnramses/golfing_madness_puzzle_solver)
for one of the puzzles and extended to cover the whole series.

## Stack
- Python 3.14, managed with `uv` (use `uv add` / `uv sync`, never bare pip)
- pytest (+ coverage), Ruff (lint + format), mypy (type check)
- GitHub Actions CI
- asyncio if needed, plus relevant pytest modules

## Commands
Run these before saying a task is done.

| Task           | Command                                                    |
|----------------|------------------------------------------------------------|
| Install        | `uv sync`                                                  |
| Run (dev)      | `uv run python ./src/puzzle.py`                            |
| Tests/Coverage | `uv run pytest --cov=src ./`                               |
| One test       | `uv run pytest tests/path.py::test_name`                   |
| Lint           | `uv run ruff check .`                                      |
| Format         | `uv run ruff format .`                                     |
| Types          | `uv run mypy src/ tests/ scripts/`                         |

CI runs lint, types, and tests on every push. Keep all three green. Check this locally using: `uv run pre-commit run --all-files`

## Instructions
- Follow the plan in @/PLAN.md
- Keep the original C++ untouched in @/cpp/main.cpp
- Python version and pytest never edit the recorded C++ solution fixture to make a test pass.

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
src/
  puzzle.py        # Main entry point
  model/           # LangGraph graph, state, checkpointer
  ...
docs/
  design/          # how it is built: components, data flow, trade-offs
  requirements/    # what the system must do (R-nnnn statements)
  specs/           # per-feature contract: goal, I/O, behavior, acceptance 
tests/
pyproject.toml
uv.lock            # UV sync file
```

## Conventions
- Type annotation hints everywhere - in src and tests; no untyped functions or parameters.
- Small commits with imperative messages, one concern each.
- Commit comments should be concise, simple language. Do not add 'co-author'.
- Ask me before adding dependencies.

## Non-goals (for now)

