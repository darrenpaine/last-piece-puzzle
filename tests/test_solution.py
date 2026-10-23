import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

import pytest

from last_piece_puzzle.solution import Solution, load_solution

ROOT = Path(__file__).parent.parent
FIXTURE = ROOT / "tests" / "fixtures" / "golfing_madness_solution_1.txt"
CPP_SOURCE = ROOT / "cpp" / "main.cpp"

# Cell count of each Golfing Madness piece; moves to the puzzle definition in SPEC-0006.
PIECE_SIZES = dict(zip("ABCDEFGHIJKLMN", (4, 3, 5, 5, 4, 4, 5, 5, 5, 5, 5, 4, 5, 5), strict=True))


@pytest.fixture
def solution() -> Solution:
    return load_solution(FIXTURE)


@pytest.mark.spec("SPEC-0002", "AT-0001")
def test_fixture_loads_grid_and_metadata(solution: Solution) -> None:
    assert len(solution.grid) == 8
    assert all(len(row) == 8 and set(row) <= set(PIECE_SIZES) for row in solution.grid)
    assert solution.grid[0] == "EEEHJJJJ"
    assert solution.metadata.keys() == {"source", "start_piece", "moves", "runtime"}
    assert solution.metadata["start_piece"] == "E"
    assert solution.metadata["moves"] == "1529410"


@pytest.mark.spec("SPEC-0002", "AT-0002")
@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (["A A A"] + ["A B C D E F G H"] * 7, "cells"),
        (["A B C D E F G H"] * 9, "rows"),
        (["A B C D E F G Z"] + ["A B C D E F G H"] * 7, "unknown"),
    ],
    ids=["short-row", "ninth-row", "unknown-letter"],
)
def test_malformed_file_raises(tmp_path: Path, rows: list[str], message: str) -> None:
    path = tmp_path / "bad.txt"
    path.write_text("# source: test\n" + "\n".join(rows) + "\n")
    with pytest.raises(ValueError, match=message):
        load_solution(path)


@pytest.mark.spec("SPEC-0002", "AT-0003")
def test_each_piece_has_its_cell_count(solution: Solution) -> None:
    assert Counter("".join(solution.grid)) == PIECE_SIZES


@pytest.mark.spec("SPEC-0002", "AT-0003")
@pytest.mark.parametrize("letter", sorted(PIECE_SIZES))
def test_each_piece_is_connected(solution: Solution, letter: str) -> None:
    cells = {
        (r, c)
        for r, row in enumerate(solution.grid)
        for c, cell in enumerate(row)
        if cell == letter
    }
    start = next(iter(cells))
    seen = {start}
    todo = [start]
    while todo:
        r, c = todo.pop()
        for step in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if step in cells and step not in seen:
                seen.add(step)
                todo.append(step)
    assert seen == cells


@pytest.mark.spec("SPEC-0002", "AT-0004")
@pytest.mark.skipif(shutil.which("g++") is None, reason="g++ not installed")
def test_cpp_solver_reproduces_fixture(solution: Solution, tmp_path: Path) -> None:
    binary = tmp_path / "hercules"
    subprocess.run(["g++", "-O2", str(CPP_SOURCE), "-o", str(binary)], check=True)
    # The solver pauses on getchar() after each solution.
    run = subprocess.run(
        [str(binary)], input="\n" * 20, capture_output=True, text=True, check=True, timeout=120
    )
    match = re.search(r"Board at Move (\d+):\n.*\n((?:[A-N.] ){8}\n){8}", run.stdout)
    assert match, run.stdout
    grid_lines = match.group(0).splitlines()[2:]
    assert tuple(line.replace(" ", "") for line in grid_lines) == solution.grid
    assert match.group(1) == solution.metadata["moves"]
