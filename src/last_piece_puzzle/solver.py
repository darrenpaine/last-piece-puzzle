"""Depth-first solver ported from cpp/main.cpp (SPEC-0003, SPEC-0005, SPEC-0006, SPEC-0007)."""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Piece, Placement
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution


@dataclass(frozen=True)
class FoundSolution:
    solution: Solution
    start_piece: str
    found_at_move: int
    times_found: int = 1


@dataclass(frozen=True)
class SolveResult:
    solutions: tuple[FoundSolution, ...]  # in the order first found
    boards_found: int  # full boards, counting repeats
    moves: int


class StartCallback(Protocol):
    """Called when the search starts with a new piece at (0, 0)."""

    def __call__(self, letter: str, /) -> None: ...


class SolutionCallback(Protocol):
    """Called with the number (from 1) and details of each new distinct solution."""

    def __call__(self, number: int, found: FoundSolution, /) -> None: ...


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

    def reset(self, on_solution: SolutionCallback | None = None) -> None:
        """Empty the board and forget the moves and solutions so far."""
        self.board = Board(self.border)
        self.used: set[str] = set()
        self.moves = 0
        self.boards = 0
        self.found: dict[tuple[str, ...], FoundSolution] = {}
        self.start = ""
        self._on_solution = on_solution

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
            self.start = piece.letter
            self.search(piece, 0, 0)
        return SolveResult(tuple(self.found.values()), self.boards, self.moves)

    def start_order(self, start_pieces: Sequence[str] | None) -> list[Piece]:
        order = self.pieces.search_order
        return [p for p in order if start_pieces is None or p.letter in start_pieces]

    def search(self, piece: Piece, row: int, col: int) -> None:
        """Try every placement of `piece` on (row, col) (C++ CheckFit)."""
        for placement in self.placements[piece.letter]:
            if self.board.fits(placement, row, col):
                self.descend(piece, placement, row, col)

    def descend(self, piece: Piece, placement: Placement, row: int, col: int) -> None:
        """Place a fitting placement, search the rest, then take it off; full boards are kept."""
        board = self.board
        board.place(piece.letter, placement, row, col)
        self.used.add(piece.letter)
        self.moves += 1
        if len(self.used) == len(self.pieces):
            self._record()
        elif (free := board.first_free()) is not None:
            for nxt in self.pieces.search_order:
                if nxt.letter not in self.used:
                    self.search(nxt, *free)
        board.remove(placement, row, col)
        self.used.discard(piece.letter)
        self.moves += 1

    def _record(self) -> None:
        """Keep a full board; an equal letter grid is the same solution found again."""
        self.boards += 1
        grid = self.board.grid()
        found = self.found.get(grid)
        if found is not None:
            self.found[grid] = replace(found, times_found=found.times_found + 1)
            return
        found = FoundSolution(Solution(grid=grid), self.start, self.moves)
        self.found[grid] = found
        if self._on_solution:
            self._on_solution(len(self.found), found)


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
