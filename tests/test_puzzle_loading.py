import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from last_piece_puzzle import main, puzzles

BROKEN = {
    "syntax": "PUZZLE = (\n",
    "import": "import last_piece_puzzle.does_not_exist\n",
    "missing": "NAME = 'no PUZZLE here'\n",
    "wrongtype": "PUZZLE = 42\n",
    "invalid": (
        "from last_piece_puzzle.pieces import Border, Tab\n"
        "from last_piece_puzzle.puzzle import Puzzle\n"
        "PUZZLE = Puzzle('Empty', (), Border((Tab.IN,), (Tab.IN,), (Tab.IN,), (Tab.IN,)))\n"
    ),
}


@pytest.fixture
def broken_puzzles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Add a folder of broken `<key>_puzzle.py` modules to the puzzles package."""
    for key, source in BROKEN.items():
        (tmp_path / f"{key}{puzzles.SUFFIX}.py").write_text(source)
    monkeypatch.setattr(puzzles, "__path__", [*puzzles.__path__, str(tmp_path)])
    yield
    for key in BROKEN:
        sys.modules.pop(f"{puzzles.__name__}.{key}{puzzles.SUFFIX}", None)


@pytest.mark.spec("SPEC-0006", "AT-0007")
@pytest.mark.usefixtures("broken_puzzles")
@pytest.mark.parametrize("key", sorted(BROKEN))
def test_broken_puzzle_raises_value_error(key: str) -> None:
    assert key in puzzles.available()
    with pytest.raises(ValueError, match=f"puzzle '{key}' cannot be loaded"):
        puzzles.load(key)


@pytest.mark.spec("SPEC-0006", "AT-0007")
@pytest.mark.usefixtures("broken_puzzles")
def test_list_marks_broken_puzzles(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--list"])
    out = capsys.readouterr().out
    assert "golfing_madness: Golfing Madness" in out
    for key in BROKEN:
        assert f"{key}: cannot load (" in out


@pytest.mark.spec("SPEC-0006", "AT-0007")
@pytest.mark.usefixtures("broken_puzzles")
def test_menu_marks_broken_puzzles(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "q")
    main([])
    out = capsys.readouterr().out
    assert "Golfing Madness (golfing_madness)" in out
    assert "syntax: cannot load (" in out


@pytest.mark.spec("SPEC-0006", "AT-0007")
@pytest.mark.usefixtures("broken_puzzles")
def test_solving_broken_puzzle_exits_1(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["missing"])
    assert exit_info.value.code == 1
    assert "last-piece-puzzle: puzzle 'missing' cannot be loaded" in capsys.readouterr().err
