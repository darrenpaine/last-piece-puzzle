from pathlib import Path

import pytest

from last_piece_puzzle import solver
from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import Solution, load_solution, save_solution
from last_piece_puzzle.solver import SEARCH_METHODS, Method, check_solution

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE
FIXTURES = [
    load_solution(Path(__file__).parent / "fixtures" / f"golfing_madness_solution_{n}.txt")
    for n in range(1, 6)
]
GRIDS = [fixture.grid for fixture in FIXTURES]
# Start piece and first-found move of each solution, in the default mode (SPEC-0007 table).
FIRST_FOUND = [("E", 882594), ("E", 899460), ("C", 1281818), ("C", 1320874), ("A", 1377280)]

# A 2x1 piece that is the same after a 180 degree turn, tabs included.
SYMMETRIC_DOMINO = Piece(
    "A",
    "domino",
    (Bit(0, 0, north=OUT, west=IN, south=IN, east=NONE), Bit(0, 1, IN, NONE, OUT, IN)),
)


@pytest.mark.spec("SPEC-0007", "AT-0001")
def test_golfing_madness_distinct_rotations() -> None:
    rotations = {p.letter: p.distinct_rotations for p in PUZZLE.pieces}
    assert rotations == {letter: 2 if letter in "DH" else 4 for letter in "ABCDEFGHIJKLMN"}


@pytest.mark.spec("SPEC-0007", "AT-0001")
def test_distinct_rotations_of_small_pieces() -> None:
    plus = Piece(
        "P",
        "plus",
        (
            Bit(0, 0, NONE, NONE, NONE, NONE),
            Bit(-1, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, OUT, OUT, OUT),
            Bit(0, -1, OUT, OUT, OUT, NONE),
            Bit(0, 1, OUT, NONE, OUT, OUT),
        ),
    )
    plain = Piece("B", "domino", (Bit(0, 0, OUT, IN, IN, NONE), Bit(0, 1, OUT, NONE, OUT, OUT)))
    assert plus.distinct_rotations == 1
    assert SYMMETRIC_DOMINO.distinct_rotations == 2
    assert plain.distinct_rotations == 4
    # Kept rotations stay in C++ order, each with every anchor bit.
    assert SYMMETRIC_DOMINO.distinct_placements == SYMMETRIC_DOMINO.placements[:4]


@pytest.mark.spec("SPEC-0007", "AT-0002")
@pytest.mark.parametrize(("all_rotations", "times_found", "moves"), [(False, 1, 2), (True, 2, 4)])
@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_symmetric_piece_found_once(
    all_rotations: bool, times_found: int, moves: int, method: Method
) -> None:
    # The border accepts the domino lying flat; turning it 180 degrees gives the same placement.
    border = Border(top=(IN, OUT), left=(OUT,), right=(OUT,), bottom=(OUT, IN))
    puzzle = Puzzle("domino", (SYMMETRIC_DOMINO,), border)
    result = solver.solve(puzzle, all_rotations=all_rotations, method=method)
    assert [found.solution.grid for found in result.solutions] == [("AA",)]
    assert result.solutions[0].times_found == times_found
    assert result.boards_found == times_found
    assert result.moves == moves


@pytest.mark.spec("SPEC-0007", "AT-0003")
def test_save_then_load_round_trip(tmp_path: Path) -> None:
    solution = Solution(GRIDS[1], {"source": "test", "start_piece": "E"})
    path = tmp_path / "solution.txt"
    save_solution(path, solution)
    assert load_solution(path) == solution


@pytest.mark.spec("SPEC-0007", "AT-0004")
def test_fixtures_are_valid_and_different() -> None:
    assert all(check_solution(PUZZLE, grid) for grid in GRIDS)
    assert len(set(GRIDS)) == 5
    for fixture, (start, move) in zip(FIXTURES[1:], FIRST_FOUND[1:], strict=True):
        assert fixture.metadata == {
            "source": "python solve",
            "start_piece": start,
            "found_at_move": str(move),
        }


@pytest.mark.spec("SPEC-0004", "AT-0001")
@pytest.mark.spec("SPEC-0007", "AT-0005")
@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_start_e_finds_first_two_fixtures(method: Method) -> None:
    started: list[str] = []
    result = solver.solve(PUZZLE, start_pieces=["E"], on_start=started.append, method=method)
    assert [found.solution.grid for found in result.solutions] == GRIDS[:2]
    assert [(f.start_piece, f.found_at_move, f.times_found) for f in result.solutions] == [
        ("E", 201634, 1),  # only the E start is counted
        ("E", 218500, 1),
    ]
    assert result.moves == 335338
    assert started == ["E"]


@pytest.mark.spec("SPEC-0007", "AT-0006")
@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_cpp_mode_start_a(method: Method) -> None:
    result = solver.solve(PUZZLE, start_pieces=["A"], all_rotations=True, method=method)
    assert len(result.solutions) == 1
    found = result.solutions[0]
    assert found.solution.grid == GRIDS[4]
    assert (found.start_piece, found.found_at_move, found.times_found) == ("A", 22970, 4)


@pytest.mark.spec("SPEC-0004", "AT-0005")
@pytest.mark.spec("SPEC-0007", "AT-0007")
@pytest.mark.slow
@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_default_finds_all_five(method: Method) -> None:
    result = solver.solve(PUZZLE, method=method)
    assert [found.solution.grid for found in result.solutions] == GRIDS
    assert [(f.start_piece, f.found_at_move) for f in result.solutions] == FIRST_FOUND
    assert all(found.times_found == 1 for found in result.solutions)
    assert (result.boards_found, result.moves) == (5, 1430150)


@pytest.mark.spec("SPEC-0003", "AT-0005")
@pytest.mark.spec("SPEC-0007", "AT-0008")
@pytest.mark.slow
@pytest.mark.parametrize("method", SEARCH_METHODS)
def test_cpp_mode_matches_cpp(method: Method) -> None:
    result = solver.solve(PUZZLE, all_rotations=True, method=method)
    first = result.solutions[0]
    assert first.solution.grid == GRIDS[0]
    assert first.start_piece == FIXTURES[0].metadata["start_piece"]
    assert str(first.found_at_move) == FIXTURES[0].metadata["moves"]
    assert [found.solution.grid for found in result.solutions] == GRIDS
    assert all(found.times_found == 4 for found in result.solutions)
    assert (result.boards_found, result.moves) == (20, 2654638)
