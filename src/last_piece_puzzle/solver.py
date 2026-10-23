"""Depth-first solver ported from cpp/main.cpp (SPEC-0003, SPEC-0005 to SPEC-0007, SPEC-0009)."""

from collections.abc import Sequence
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

from last_piece_puzzle.board import Board
from last_piece_puzzle.engine import Candidates, Engine
from last_piece_puzzle.engine import FoundSolution as FoundSolution
from last_piece_puzzle.engine import SolutionCallback as SolutionCallback
from last_piece_puzzle.pieces import Piece
from last_piece_puzzle.puzzle import Puzzle


@dataclass(frozen=True)
class SolveResult:
    solutions: tuple[FoundSolution, ...]  # in the order first found
    boards_found: int  # full boards, counting repeats
    moves: int


class StartCallback(Protocol):
    """Called when the search starts with a new piece at (0, 0)."""

    def __call__(self, letter: str, /) -> None: ...


class Solver:
    def __init__(self, puzzle: Puzzle, all_rotations: bool = False) -> None:
        """`all_rotations` tries all 4 rotations of every piece, as the C++ does."""
        self.puzzle = puzzle
        self.all_rotations = all_rotations
        self.pieces = puzzle.piece_set
        self.border = puzzle.border
        self.placements = {
            p.letter: p.placements if all_rotations else p.distinct_placements for p in self.pieces
        }
        self.reset()

    @cached_property
    def candidates(self) -> Candidates:
        """The placements that could fit at each cell, built once (SPEC-0009)."""
        return Candidates(self.puzzle, self.all_rotations)

    def reset(self, on_solution: SolutionCallback | None = None) -> None:
        """Empty the board and forget the moves and solutions so far."""
        self.engine = Engine(self.candidates, on_solution)

    @property
    def moves(self) -> int:
        return self.engine.moves

    @property
    def boards(self) -> int:
        return self.engine.boards

    @property
    def found(self) -> dict[tuple[str, ...], FoundSolution]:
        return self.engine.found

    def solve(
        self,
        start_pieces: Sequence[str] | None = None,
        on_start: StartCallback | None = None,
        on_solution: SolutionCallback | None = None,
        workers: int | None = None,
    ) -> SolveResult:
        """Find every solution, trying each start piece at (0, 0) in C++ order (N to A).

        `start_pieces` limits which pieces are tried at (0, 0); the search after that is unchanged.
        `on_solution` is called with the number and details of each new distinct solution.
        `workers` above 1 splits the search over that many processes (SPEC-0008), same result.
        """
        if workers is not None and workers > 1:
            from last_piece_puzzle import parallel  # imports this module

            return parallel.solve(self, start_pieces, on_start, on_solution, workers)
        self.reset(on_solution)
        for piece in self.start_order(start_pieces):
            if on_start:
                on_start(piece.letter)
            self.engine.start = piece.letter
            self.engine.search(piece.letter, 0)
        return SolveResult(tuple(self.found.values()), self.boards, self.moves)

    def start_order(self, start_pieces: Sequence[str] | None) -> list[Piece]:
        order = self.pieces.search_order
        return [p for p in order if start_pieces is None or p.letter in start_pieces]


def solve(
    puzzle: Puzzle,
    start_pieces: Sequence[str] | None = None,
    on_start: StartCallback | None = None,
    on_solution: SolutionCallback | None = None,
    all_rotations: bool = False,
    workers: int | None = None,
) -> SolveResult:
    return Solver(puzzle, all_rotations).solve(start_pieces, on_start, on_solution, workers)


def check_solution(puzzle: Puzzle, grid: Sequence[str]) -> bool:
    """True if the grid can be built from the puzzle's pieces with every tab fitting."""
    return Board.from_grid(puzzle, grid) is not None
