import pytest

from last_piece_puzzle import main


def test_main_prints_greeting(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    assert "last-piece-puzzle" in capsys.readouterr().out
