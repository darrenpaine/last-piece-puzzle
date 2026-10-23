import pytest

from last_piece_puzzle import solve_puzzle, solver
from last_piece_puzzle.output import Output
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import Solution
from last_piece_puzzle.solver import (
    FoundSolution,
    Method,
    SolutionCallback,
    SolveResult,
    StartCallback,
)

FOUND = FoundSolution(Solution(("A",)), "A", 5)
RESULT = SolveResult((FOUND,), 1, 9)


class RecordingOutput(Output):
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def header(self, puzzle: Puzzle) -> None:
        self.calls.append(("header", puzzle.name))

    def on_start(self, letter: str, /) -> None:
        self.calls.append(("start", letter))

    def on_solution(self, number: int, found: FoundSolution, /) -> None:
        self.calls.append(("solution", number, found))

    def finish(
        self, puzzle: Puzzle, result: SolveResult, seconds: float, workers: int, method: Method
    ) -> None:
        self.calls.append(("finish", puzzle.name, result, workers, method))


@pytest.mark.spec("SPEC-0008", "AT-0008")
def test_solve_puzzle_sends_everything_to_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_solve(
        puzzle: Puzzle,
        *,
        on_start: StartCallback,
        on_solution: SolutionCallback,
        workers: int,
        method: Method,
    ) -> SolveResult:
        assert method == "dlx"
        on_start("B")
        on_start("A")
        on_solution(1, FOUND)
        return RESULT

    monkeypatch.setattr(solver, "solve", fake_solve)
    output = RecordingOutput()
    solve_puzzle(PUZZLE, workers=3, output=output, method="dlx")
    assert output.calls == [
        ("header", "Golfing Madness"),
        ("start", "B"),
        ("start", "A"),
        ("solution", 1, FOUND),
        ("finish", "Golfing Madness", RESULT, 3, "dlx"),
    ]


@pytest.mark.spec("SPEC-0008", "AT-0008")
def test_output_is_abstract() -> None:
    with pytest.raises(TypeError):
        Output()  # type: ignore[abstract]
