import os
import time
from pathlib import Path

import pytest

from last_piece_puzzle import METHODS, main, parallel, solver
from last_piece_puzzle.board import Board
from last_piece_puzzle.engine import FastSolver
from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.puzzles.golfing_madness_puzzle import PUZZLE
from last_piece_puzzle.solution import load_solution
from last_piece_puzzle.solver import FoundSolution, Method, Solver, SolveResult

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE
GRIDS = [
    load_solution(Path(__file__).parent / "fixtures" / f"golfing_madness_solution_{n}.txt").grid
    for n in range(1, 6)
]
ONE_BY_ONE = Border(top=(IN,), left=(IN,), right=(IN,), bottom=(IN,))
ONE_BY_TWO = Border(top=(IN, IN), left=(IN,), right=(IN,), bottom=(IN, IN))
ALL_OUT = Bit(0, 0, OUT, OUT, OUT, OUT)
TURNED = Bit(0, 0, north=OUT, west=IN, south=OUT, east=OUT)
SYMMETRIC_DOMINO = Piece(
    "A", "domino", (Bit(0, 0, OUT, IN, IN, NONE), Bit(0, 1, IN, NONE, OUT, IN))
)
SMALL_PUZZLES = {
    "one-cell": Puzzle("one cell", (Piece("A", "a", (ALL_OUT,)),), ONE_BY_ONE),
    "no-solution": Puzzle(
        "clash", (Piece("A", "a", (ALL_OUT,)), Piece("B", "b", (ALL_OUT,))), ONE_BY_TWO
    ),
    "two-solutions": Puzzle(
        "rotate", (Piece("A", "a", (ALL_OUT,)), Piece("B", "b", (TURNED,))), ONE_BY_TWO
    ),
    "symmetric": Puzzle(
        "domino",
        (SYMMETRIC_DOMINO,),
        Border(top=(IN, OUT), left=(OUT,), right=(OUT,), bottom=(OUT, IN)),
    ),
}

Calls = list[tuple[str, object]]


def solve_with_calls(puzzle: Puzzle, **options: object) -> tuple[SolveResult, Calls]:
    calls: Calls = []

    def on_solution(number: int, found: FoundSolution) -> None:
        calls.append(("solution", (number, found)))

    result = solver.solve(
        puzzle,
        on_start=lambda letter: calls.append(("start", letter)),
        on_solution=on_solution,
        **options,  # type: ignore[arg-type]
    )
    return result, calls


@pytest.mark.spec("SPEC-0008", "AT-0001")
@pytest.mark.parametrize("all_rotations", [False, True])
@pytest.mark.parametrize("key", sorted(SMALL_PUZZLES))
@pytest.mark.parametrize("method", METHODS)
def test_small_puzzles_match_single_process(key: str, all_rotations: bool, method: Method) -> None:
    puzzle = SMALL_PUZZLES[key]
    expected = solve_with_calls(puzzle, all_rotations=all_rotations, method=method)
    assert (
        solve_with_calls(puzzle, all_rotations=all_rotations, workers=2, method=method) == expected
    )


@pytest.mark.spec("SPEC-0008", "AT-0002")
def test_split_gives_many_valid_tasks() -> None:
    steps = parallel.split(Solver(PUZZLE), ["E"], workers=2)
    tasks = [step for step in steps if isinstance(step, parallel.Task)]
    assert len(tasks) >= 200
    assert steps[0] == parallel.Start("E")
    for task in tasks:
        board = Board(PUZZLE.border)
        for letter, index in task.path:
            placement = PUZZLE.piece_set.by_letter[letter].distinct_placements[index]
            free = board.first_free()
            assert free is not None and board.fits(placement, *free)
            board.place(letter, placement, *free)


@pytest.mark.spec("SPEC-0008", "AT-0002")
@pytest.mark.parametrize("solver_class", [Solver, FastSolver])
def test_split_tasks_merge_to_single_process_result(solver_class: type[Solver]) -> None:
    # Running the tasks one by one in this process, then merging, must equal the plain search.
    one = solver_class(PUZZLE)
    steps = parallel.split(one, ["A"], workers=2)
    tasks = [step for step in steps if isinstance(step, parallel.Task)]
    results = iter([parallel.run_task(solver_class(PUZZLE), task) for task in tasks])
    assert parallel._merge(steps, results, None, None) == one.solve(["A"])


@pytest.mark.spec("SPEC-0008", "AT-0003")
@pytest.mark.parametrize("method", METHODS)
def test_start_e_with_two_workers(method: Method) -> None:
    result = solver.solve(PUZZLE, start_pieces=["E"], workers=2, method=method)
    assert [found.solution.grid for found in result.solutions] == GRIDS[:2]
    assert [found.found_at_move for found in result.solutions] == [201634, 218500]
    assert result.moves == 335338


@pytest.mark.spec("SPEC-0008", "AT-0004")
@pytest.mark.slow
@pytest.mark.parametrize("method", METHODS)
def test_full_solve_with_workers_matches_step_6(method: Method) -> None:
    result = solver.solve(PUZZLE, workers=4, method=method)
    assert [found.solution.grid for found in result.solutions] == GRIDS
    assert [found.found_at_move for found in result.solutions] == [
        882594,
        899460,
        1281818,
        1320874,
        1377280,
    ]
    assert (result.boards_found, result.moves) == (5, 1430150)
    cpp = solver.solve(PUZZLE, all_rotations=True, workers=4, method=method)
    assert cpp.solutions[0].found_at_move == 1529410
    assert (len(cpp.solutions), cpp.boards_found, cpp.moves) == (5, 20, 2654638)


@pytest.mark.spec("SPEC-0008", "AT-0005")
@pytest.mark.slow
@pytest.mark.skipif((os.process_cpu_count() or 1) < 4, reason="needs at least 4 CPUs")
def test_four_workers_at_least_twice_as_fast() -> None:
    started = time.perf_counter()
    solver.solve(PUZZLE, method="search")
    single = time.perf_counter() - started
    started = time.perf_counter()
    solver.solve(PUZZLE, workers=4, method="search")
    assert time.perf_counter() - started < single / 2


@pytest.mark.spec("SPEC-0008", "AT-0006")
@pytest.mark.parametrize(
    ("argv", "workers", "shown"),
    [
        (["--workers", "3"], 3, "(3 workers)"),
        (["--workers", "1"], 1, "(1 worker)"),
        ([], 7, "(7 workers)"),
    ],
)
def test_cli_passes_workers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    workers: int,
    shown: str,
) -> None:
    seen: list[object] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        seen.append(kwargs.get("workers"))
        return SolveResult((), 0, 0)

    monkeypatch.setattr(solver, "solve", fake_solve)
    monkeypatch.setattr(os, "process_cpu_count", lambda: 7)
    main(["golfing_madness", *argv])
    assert seen == [workers]
    assert capsys.readouterr().out.rstrip().endswith(f"{shown}.")


@pytest.mark.spec("SPEC-0008", "AT-0007")
@pytest.mark.parametrize("count", ["0", "8", "100"])
def test_cli_rejects_workers_out_of_range(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], count: str
) -> None:
    monkeypatch.setattr(os, "process_cpu_count", lambda: 7)
    with pytest.raises(SystemExit) as exit_info:
        main(["golfing_madness", "--workers", count])
    assert exit_info.value.code == 2
    assert "must be between 1 and 7" in capsys.readouterr().err


@pytest.mark.spec("SPEC-0008", "AT-0007")
def test_cli_accepts_all_cpus(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[object] = []

    def fake_solve(puzzle: Puzzle, *args: object, **kwargs: object) -> SolveResult:
        seen.append(kwargs.get("workers"))
        return SolveResult((), 0, 0)

    monkeypatch.setattr(solver, "solve", fake_solve)
    monkeypatch.setattr(os, "process_cpu_count", lambda: 7)
    main(["golfing_madness", "--workers", "7"])
    assert seen == [7]
