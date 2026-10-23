import argparse
import time
from collections.abc import Sequence

from last_piece_puzzle import puzzles, solver
from last_piece_puzzle.puzzle import Puzzle


def main(argv: Sequence[str] | None = None) -> None:
    """Solve a puzzle chosen by key, or from a menu, and print its solutions."""
    keys = puzzles.available()
    parser = argparse.ArgumentParser(
        prog="last-piece-puzzle", description="Solve a Last Piece Puzzle."
    )
    parser.add_argument("puzzle", nargs="?", choices=keys, help="puzzle to solve (default: menu)")
    parser.add_argument("--list", action="store_true", help="list the available puzzles")
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
    solve_and_print(puzzle)


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


def solve_and_print(puzzle: Puzzle) -> None:
    """Find every solution, then print the key once and the numbered solutions (SPEC-0007)."""
    print(f"Last Piece Puzzle solver: {puzzle.name}")
    started = time.perf_counter()
    result = solver.solve(
        puzzle,
        on_start=lambda letter: print(f"Trying to start puzzle with piece {letter}...", flush=True),
        on_solution=lambda number, found: print(
            f"Solution {number} found starting with piece {found.start_piece}"
            f" at move {found.found_at_move}",
            flush=True,
        ),
    )
    seconds = time.perf_counter() - started
    if not result.solutions:
        print(f"No solutions found in {result.moves} moves, {seconds:.1f} s.")
        return
    print("\nKey:")
    for piece in puzzle.pieces:
        print(f"{piece.letter} = {piece.name}")
    for number, found in enumerate(result.solutions, start=1):
        print(f"\nSolution {number} (start piece {found.start_piece}):")
        for row in found.solution.grid:
            print(" ".join(row))
    count = len(result.solutions)
    plural = "solution" if count == 1 else "solutions"
    print(f"\n{count} {plural} found in {result.moves} moves, {seconds:.1f} s.")
