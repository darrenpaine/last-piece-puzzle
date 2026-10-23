import pytest

MARKED_TESTS = """
import pytest

@pytest.mark.spec("SPEC-9999", "AT-0001")
def test_fast() -> None:
    pass

@pytest.mark.slow
def test_slow() -> None:
    pass
"""


@pytest.mark.spec("SPEC-0001", "AT-0001")
def test_registered_markers_pass_strict_markers(pytester: pytest.Pytester) -> None:
    pytester.makepyprojecttoml(
        '[tool.pytest.ini_options]\nmarkers = ["spec", "slow"]\naddopts = ["--strict-markers"]\n'
    )
    pytester.makepyfile(MARKED_TESTS)
    pytester.runpytest().assert_outcomes(passed=2)


@pytest.mark.spec("SPEC-0001", "AT-0001")
def test_unknown_marker_fails_strict_markers(pytester: pytest.Pytester) -> None:
    pytester.makepyfile(
        "import pytest\n\n@pytest.mark.not_registered\ndef test_x() -> None:\n    pass\n"
    )
    pytester.runpytest("--strict-markers").assert_outcomes(errors=1)


@pytest.mark.spec("SPEC-0001", "AT-0002")
def test_not_slow_deselects_slow_tests(pytester: pytest.Pytester) -> None:
    pytester.makepyprojecttoml('[tool.pytest.ini_options]\nmarkers = ["spec", "slow"]\n')
    pytester.makepyfile(MARKED_TESTS)
    result = pytester.runpytest("-m", "not slow")
    result.assert_outcomes(passed=1, deselected=1)
