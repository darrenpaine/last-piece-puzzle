import re
from collections.abc import Callable, Iterator

import pytest

from last_piece_puzzle import main, solver
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution
from last_piece_puzzle.solver import FoundSolution, SolveResult


@pytest.fixture
def solved(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the solver and record the names of the puzzles it was asked to solve."""
    names: list[str] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        names.append(puzzle.name)
        return SolveResult((FoundSolution(Solution(("A",)), "A", 1),), 1, 2)

    monkeypatch.setattr(solver, "solve", fake_solve)
    return names


def script_input(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    """Feed `answers` to input(); after the last one, input() raises EOFError."""
    feed: Iterator[str] = iter(answers)

    def fake_input(prompt: str = "") -> str:
        print(prompt, end="")
        try:
            return next(feed)
        except StopIteration:
            raise EOFError from None

    monkeypatch.setattr("builtins.input", fake_input)


@pytest.mark.spec("SPEC-0006", "AT-0005")
def test_puzzle_key_solves_it(solved: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    main(["golfing_madness"])
    assert solved == ["Golfing Madness"]
    assert "Last Piece Puzzle solver: Golfing Madness" in capsys.readouterr().out


@pytest.mark.spec("SPEC-0006", "AT-0005")
def test_list(solved: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    main(["--list"])
    assert "golfing_madness: Golfing Madness" in capsys.readouterr().out
    assert solved == []


@pytest.mark.spec("SPEC-0006", "AT-0005")
def test_unknown_key_exits_2(solved: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["nope"])
    assert exit_info.value.code == 2
    assert "golfing_madness" in capsys.readouterr().err
    assert solved == []


@pytest.mark.spec("SPEC-0006", "AT-0006")
def test_menu_number_solves(
    monkeypatch: pytest.MonkeyPatch, solved: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    script_input(monkeypatch, ["1"])
    main([])
    out = capsys.readouterr().out
    assert "1. Golfing Madness (golfing_madness)" in out
    assert "Choose a puzzle (1-1, q to quit): " in out
    assert solved == ["Golfing Madness"]


@pytest.mark.spec("SPEC-0006", "AT-0006")
@pytest.mark.parametrize("answers", [["q"], [""], []], ids=["q", "empty", "end-of-input"])
def test_menu_quit(monkeypatch: pytest.MonkeyPatch, solved: list[str], answers: list[str]) -> None:
    script_input(monkeypatch, answers)
    main([])
    assert solved == []


@pytest.mark.spec("SPEC-0006", "AT-0006")
def test_menu_invalid_then_valid(
    monkeypatch: pytest.MonkeyPatch, solved: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    script_input(monkeypatch, ["x", "1"])
    main([])
    assert capsys.readouterr().out.count("Not a valid choice.") == 1
    assert solved == ["Golfing Madness"]


def stub_solutions(monkeypatch: pytest.MonkeyPatch, found: tuple[FoundSolution, ...]) -> None:
    """Stub the solver to report `found`, calling on_solution as the real search does."""

    def fake_solve(
        puzzle: Puzzle,
        *args: object,
        on_solution: Callable[[int, FoundSolution], None] | None = None,
        **kwargs: object,
    ) -> SolveResult:
        for number, item in enumerate(found, start=1):
            if on_solution:
                on_solution(number, item)
        return SolveResult(found, len(found), 99)

    monkeypatch.setattr(solver, "solve", fake_solve)


@pytest.mark.spec("SPEC-0007", "AT-0009")
def test_prints_found_lines_key_once_and_numbered_solutions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first = FoundSolution(Solution(("EEEHJJJJ",)), "E", 10)
    second = FoundSolution(Solution(("AKKKKNNF",)), "A", 20)
    stub_solutions(monkeypatch, (first, second))
    main(["golfing_madness"])
    out = capsys.readouterr().out
    lines = [
        "Solution 1 found starting with piece E at move 10",
        "Solution 2 found starting with piece A at move 20",
        "Key:",
        "A = Bluehat",
        "N = ZigZag",
        "Solution 1 (start piece E):",
        "E E E H J J J J",
        "Solution 2 (start piece A):",
        "A K K K K N N F",
    ]
    positions = [out.index(line) for line in lines]
    assert positions == sorted(positions)
    assert out.count("Key:") == 1
    assert re.search(r"\n2 solutions found in 99 moves, \d+\.\d s \(\d+ workers?\)\.\n$", out)


@pytest.mark.spec("SPEC-0007", "AT-0009")
def test_prints_only_no_solutions_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    stub_solutions(monkeypatch, ())
    main(["golfing_madness"])
    out = capsys.readouterr().out
    assert "Key:" not in out
    assert re.search(r"No solutions found in 99 moves, \d+\.\d s \(\d+ workers?\)\.\n$", out)


@pytest.mark.spec("SPEC-0009", "AT-0004")
@pytest.mark.parametrize(
    ("argv", "method"), [([], "fastsearch"), (["--method", "search"], "search")]
)
def test_cli_passes_method(monkeypatch: pytest.MonkeyPatch, argv: list[str], method: str) -> None:
    seen: list[object] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        seen.append(kwargs.get("method"))
        return SolveResult((), 0, 0)

    monkeypatch.setattr(solver, "solve", fake_solve)
    main(["golfing_madness", *argv])
    assert seen == [method]


@pytest.mark.spec("SPEC-0009", "AT-0004")
def test_cli_rejects_unknown_method(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["golfing_madness", "--method", "nope"])
    assert exit_info.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
