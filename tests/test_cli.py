from collections.abc import Iterator

import pytest

from last_piece_puzzle import main, solver
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution
from last_piece_puzzle.solver import SolveResult


@pytest.fixture
def solved(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Stub the solver and record the names of the puzzles it was asked to solve."""
    names: list[str] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        names.append(puzzle.name)
        return SolveResult(Solution(("A",)), "A", 1)

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
