# SPEC-0001: Spec and id conventions

Status: Done

## Goal
Each requirement can be traced from its spec to the tests that check it.

## Spec file
- Path: `docs/specs/SPEC-nnnn-<short-name>.md`, numbered in order and never reused.
- Add each new spec to the table in `docs/specs/README.md`.
- Sections: Goal, Inputs/Outputs, Behaviour, Acceptance tests, Out of scope.

## Ids
- Behaviour items are `B-nnnn` and acceptance tests are `AT-nnnn`.
- Ids are numbered per spec (each spec starts at 0001), so always write them with the spec id,
  e.g. `SPEC-0002 B-0003`.
- Once a spec is reviewed, its ids never change meaning. Retire an id rather than reuse it.

## Behaviour
- B-0001: Every acceptance test in a spec has a pytest test marked
  `@pytest.mark.spec("SPEC-nnnn", "AT-nnnn")`.
- B-0002: Tests that take longer than a few seconds are also marked `@pytest.mark.slow`.
  CI runs `-m "not slow"`.
- B-0003: The `spec` and `slow` markers are registered in `pyproject.toml`, so unknown markers fail
  (`--strict-markers`).

## Acceptance tests
- AT-0001: `uv run pytest --strict-markers` passes with the `spec` and `slow` markers in use.
- AT-0002: `uv run pytest -m "not slow"` deselects the tests marked slow.

## Out of scope
A tool that checks every AT has a test (it could be added later).
