"""Split the search into tasks, run them on worker processes, merge in search order (SPEC-0008).

How the split works, using Golfing Madness as the example:

- Depth 1: every start piece is tried at (0, 0), in search order (N to A). Each placement of it that
  fits becomes a task, e.g. E has 2 placements that fit in the corner: ("E", 11) and ("E", 13).
  That gives only 15 tasks, and the E and C ones take about 4 s each, so they would not balance.
- Depth 2: under each start placement, every unused piece is tried at the next free cell. Each one
  that fits becomes a task with a path of two placements, e.g. (("E", 11), ("M", 0)): 114 tasks.
- Depth 3 gives 1,101 tasks, and depth 4 gives 4,408, of which E has 1,079, C 574 and A 52.

`split` goes one level deeper until there are at least `TASKS_PER_WORKER` tasks per worker (16
workers: depth 4). A worker places a task's path, each placement at the first free cell, then
searches everything below it. A `Start` step marks each new start piece, and the `1` steps stand for
placing and removing the placements above the tasks. So `_merge` can rebuild the move count and
solution order of a single-process search exactly.
"""

from collections.abc import Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace

from last_piece_puzzle.board import Board
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solver import (
    FoundSolution,
    SolutionCallback,
    Solver,
    SolveResult,
    StartCallback,
)

TASKS_PER_WORKER = 100

# Placements from the empty board, each at the first free cell: (letter, index into placements).
Path = tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class Task:
    path: Path


@dataclass(frozen=True)
class Start:
    """The search reaches a new start piece here (for `on_start`)."""

    letter: str


@dataclass(frozen=True)
class TaskResult:
    moves: int
    boards: int
    found: tuple[FoundSolution, ...]  # found_at_move counted from the start of the task


# In search order: a new start piece, a task, or moves made by placing or removing a prefix.
Step = Start | Task | int


def split(solver: Solver, start_pieces: Sequence[str] | None, workers: int) -> list[Step]:
    """Expand the tree one level at a time until it gives `TASKS_PER_WORKER * workers` tasks."""
    target = TASKS_PER_WORKER * workers
    depth = 1
    steps = _split_at(solver, start_pieces, depth)
    while (count := _count_tasks(steps)) < target:
        deeper = _split_at(solver, start_pieces, depth + 1)
        if _count_tasks(deeper) == count:  # nothing can grow any further
            break
        steps, depth = deeper, depth + 1
    return steps


def _count_tasks(steps: list[Step]) -> int:
    return sum(isinstance(step, Task) for step in steps)


def _split_at(solver: Solver, start_pieces: Sequence[str] | None, depth: int) -> list[Step]:
    steps: list[Step] = []
    board = Board(solver.border)
    used: set[str] = set()
    path: list[tuple[str, int]] = []

    def walk(letters: list[str], row: int, col: int, level: int) -> None:
        for letter in letters:
            if level == 1:
                steps.append(Start(letter))
            for index, placement in enumerate(solver.placements[letter]):
                if not board.fits(placement, row, col):
                    continue
                path.append((letter, index))
                if level == depth or len(used) + 1 == len(solver.pieces):
                    steps.append(Task(tuple(path)))
                else:
                    board.place(letter, placement, row, col)
                    used.add(letter)
                    steps.append(1)
                    free = board.first_free()
                    assert free is not None  # the board is not full: pieces are left
                    rest = [p.letter for p in solver.pieces.search_order if p.letter not in used]
                    walk(rest, *free, level + 1)
                    board.remove(placement, row, col)
                    used.discard(letter)
                    steps.append(1)
                path.pop()

    walk([p.letter for p in solver.start_order(start_pieces)], 0, 0, 1)
    return steps


_worker: Solver | None = None


def _init_worker(puzzle: Puzzle, all_rotations: bool) -> None:
    global _worker
    _worker = Solver(puzzle, all_rotations)


def run_task(solver: Solver, task: Task) -> TaskResult:
    """Place the task's prefix without counting moves, then search below its last placement."""
    solver.reset()
    solver.engine.run_path(task.path)
    return TaskResult(solver.moves, solver.boards, tuple(solver.found.values()))


def _run_task(task: Task) -> TaskResult:
    assert _worker is not None, "worker not initialised"
    return run_task(_worker, task)


def solve(
    solver: Solver,
    start_pieces: Sequence[str] | None,
    on_start: StartCallback | None,
    on_solution: SolutionCallback | None,
    workers: int,
) -> SolveResult:
    steps = split(solver, start_pieces, workers)
    tasks = [step for step in steps if isinstance(step, Task)]
    with ProcessPoolExecutor(
        workers, initializer=_init_worker, initargs=(solver.puzzle, solver.all_rotations)
    ) as pool:
        return _merge(steps, pool.map(_run_task, tasks), on_start, on_solution)


def _merge(
    steps: list[Step],
    results: Iterator[TaskResult],
    on_start: StartCallback | None,
    on_solution: SolutionCallback | None,
) -> SolveResult:
    """Walk the steps in search order, adding moves and solutions as the search would have."""
    moves = 0
    boards = 0
    found: dict[tuple[str, ...], FoundSolution] = {}
    for step in steps:
        if isinstance(step, Start):
            if on_start:
                on_start(step.letter)
        elif isinstance(step, Task):
            result = next(results)
            for local in result.found:
                grid = local.solution.grid
                if grid in found:
                    earlier = found[grid]
                    found[grid] = replace(
                        earlier, times_found=earlier.times_found + local.times_found
                    )
                    continue
                found[grid] = replace(local, found_at_move=moves + local.found_at_move)
                if on_solution:
                    on_solution(len(found), found[grid])
            moves += result.moves
            boards += result.boards
        else:
            moves += step
    return SolveResult(tuple(found.values()), boards, moves)
