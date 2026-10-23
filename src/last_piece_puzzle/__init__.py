import argparse
import os
import time
from collections.abc import Callable, Sequence

from last_piece_puzzle import puzzles, solver
from last_piece_puzzle.output import ConsoleOutput, Output
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solver import Method

METHODS: tuple[Method, ...] = ("dlx", "fastsearch", "search")


def main(argv: Sequence[str] | None = None) -> None:
    """Solve a puzzle chosen by key, or from a menu, and print its solutions."""
    keys = puzzles.available()
    cpus = os.process_cpu_count() or 1
    parser = argparse.ArgumentParser(
        prog="last-piece-puzzle", description="Solve a Last Piece Puzzle."
    )
    parser.add_argument("puzzle", nargs="?", choices=keys, help="puzzle to solve (default: menu)")
    parser.add_argument("--list", action="store_true", help="list the available puzzles")
    parser.add_argument(
        "--workers",
        type=worker_count(cpus),
        default=cpus,
        help=f"worker processes for the search, 1 to {cpus} (default: {cpus}; 1 = single process)",
    )
    parser.add_argument(
        "--method",
        choices=METHODS,
        default="dlx",
        help=(
            "dlx: exact cover, fastest; fastsearch: fast depth-first search;"
            " search: the original port of the C++ (default: dlx)"
        ),
    )
    args = parser.parse_args(argv)
    if args.list:
        for key in keys:
            print(describe(key))
        return
    chosen: str | None = args.puzzle or choose(keys)
    if chosen is None:
        return
    try:
        puzzle = puzzles.load(chosen)
    except ValueError as error:
        parser.exit(1, f"last-piece-puzzle: {error}\n")
    solve_puzzle(puzzle, args.workers, method=args.method)


def worker_count(cpus: int) -> Callable[[str], int]:
    """An argparse type for `--workers`: a whole number from 1 to `cpus` (SPEC-0008 B-0007)."""

    def parse(text: str) -> int:
        value = int(text)
        if not 1 <= value <= cpus:
            raise argparse.ArgumentTypeError(f"must be between 1 and {cpus}")
        return value

    return parse


def describe(key: str) -> str:
    """`key: name`, or `key: cannot load (reason)` so one broken puzzle does not stop the others."""
    try:
        return f"{key}: {puzzles.load(key).name}"
    except ValueError as error:
        return f"{key}: cannot load ({error})"


def choose(keys: Sequence[str]) -> str | None:
    """Ask for a puzzle from a numbered menu; None to quit (SPEC-0006 B-0005)."""
    for number, key in enumerate(keys, start=1):
        try:
            print(f"{number}. {puzzles.load(key).name} ({key})")
        except ValueError:
            print(f"{number}. {describe(key)}")
    while True:
        try:
            answer = input(f"Choose a puzzle (1-{len(keys)}, q to quit): ").strip()
        except EOFError:
            print()
            return None
        if answer in ("", "q"):
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(keys):
            return keys[int(answer) - 1]
        print("Not a valid choice.")


def solve_puzzle(
    puzzle: Puzzle, workers: int = 1, output: Output | None = None, method: Method = "fastsearch"
) -> None:
    """Solve the puzzle, sending progress and results to `output` (default: the console)."""
    output = output or ConsoleOutput()
    output.header(puzzle)
    started = time.perf_counter()
    result = solver.solve(
        puzzle,
        on_start=output.on_start,
        on_solution=output.on_solution,
        workers=workers,
        method=method,
    )
    output.finish(puzzle, result, time.perf_counter() - started, workers, method)
