"""Where a solve's progress and results go (SPEC-0008). `ConsoleOutput` prints them."""

from abc import ABC, abstractmethod

from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solver import FoundSolution, Method, SolveResult


class Output(ABC):
    """Receives a solve as it happens; its `on_start` / `on_solution` are the solver callbacks."""

    @abstractmethod
    def header(self, puzzle: Puzzle) -> None: ...

    @abstractmethod
    def on_start(self, letter: str, /) -> None: ...

    @abstractmethod
    def on_solution(self, number: int, found: FoundSolution, /) -> None: ...

    @abstractmethod
    def finish(
        self, puzzle: Puzzle, result: SolveResult, seconds: float, workers: int, method: Method
    ) -> None: ...


class ConsoleOutput(Output):
    """Progress lines while searching, then the key once and the numbered solutions (SPEC-0007)."""

    def header(self, puzzle: Puzzle) -> None:
        print(f"Last Piece Puzzle solver: {puzzle.name}")

    def on_start(self, letter: str, /) -> None:
        print(f"Trying to start puzzle with piece {letter}...", flush=True)

    def on_solution(self, number: int, found: FoundSolution, /) -> None:
        print(
            f"Solution {number} found starting with piece {found.start_piece}"
            f" at move {found.found_at_move}",
            flush=True,
        )

    def finish(
        self, puzzle: Puzzle, result: SolveResult, seconds: float, workers: int, method: Method
    ) -> None:
        if method == "exactcover":
            done = f"{result.moves} rows chosen, {seconds:.1f} s (Algorithm X)"
        else:
            used = f"{workers} {'worker' if workers == 1 else 'workers'}"
            done = f"{result.moves} moves, {seconds:.1f} s ({used})"
        if not result.solutions:
            print(f"No solutions found in {done}.")
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
        print(f"\n{count} {plural} found in {done}.")
