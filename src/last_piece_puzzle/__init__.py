import argparse
from collections.abc import Sequence

from last_piece_puzzle import puzzles, solver
from last_piece_puzzle.puzzle import Puzzle


def main(argv: Sequence[str] | None = None) -> None:
    """Solve a puzzle chosen by key, or from a menu, and print it in the C++ layout."""
    keys = puzzles.available()
    parser = argparse.ArgumentParser(
        prog="last-piece-puzzle", description="Solve a Last Piece Puzzle."
    )
    parser.add_argument("puzzle", nargs="?", choices=keys, help="puzzle to solve (default: menu)")
    parser.add_argument("--list", action="store_true", help="list the available puzzles")
    args = parser.parse_args(argv)
    if args.list:
        for key in keys:
            print(f"{key}: {puzzles.load(key).name}")
        return
    chosen: str | None = args.puzzle or choose(keys)
    if chosen is not None:
        solve_and_print(puzzles.load(chosen))


def choose(keys: Sequence[str]) -> str | None:
    """Ask for a puzzle from a numbered menu; None to quit (SPEC-0006 B-0005)."""
    for number, key in enumerate(keys, start=1):
        print(f"{number}. {puzzles.load(key).name} ({key})")
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
    print(f"Last Piece Puzzle solver: {puzzle.name}")
    result = solver.solve(
        puzzle,
        on_start=lambda letter: print(f"Trying to start puzzle with piece {letter}...", flush=True),
    )
    if result.solution is None:
        print(f"Solution NOT Found in {result.moves} Moves.")
        return
    print(f"Solution FOUND starting with piece {result.start_piece}")
    print(f"\nBoard at Move {result.moves}:")
    for row in result.solution.grid:
        print(" ".join(row))
    print()
    for piece in puzzle.pieces:
        print(f"{piece.letter} = {piece.name}")
