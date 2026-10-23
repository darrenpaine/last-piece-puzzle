"""Split the search into tasks, run them on worker processes, merge in search order (SPEC-0008)."""

from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace

from last_piece_puzzle.board import Board
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solver import FoundSolution, Solver, SolveResult

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
    solver.start = task.path[0][0]
    for letter, index in task.path[:-1]:
        row, col = solver.board.first_free() or (0, 0)
        solver.board.place(letter, solver.placements[letter][index], row, col)
        solver.used.add(letter)
    letter, index = task.path[-1]
    row, col = solver.board.first_free() or (0, 0)
    piece = solver.pieces.by_letter[letter]
    solver.descend(piece, solver.placements[letter][index], row, col)
    return TaskResult(solver.moves, solver.boards, tuple(solver.found.values()))


def _run_task(task: Task) -> TaskResult:
    assert _worker is not None, "worker not initialised"
    return run_task(_worker, task)


def solve(
    solver: Solver,
    start_pieces: Sequence[str] | None,
    on_start: Callable[[str], None] | None,
    on_solution: Callable[[int, FoundSolution], None] | None,
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
    on_start: Callable[[str], None] | None,
    on_solution: Callable[[int, FoundSolution], None] | None,
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
