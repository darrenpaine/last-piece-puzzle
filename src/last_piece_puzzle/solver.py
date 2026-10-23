"""Depth-first solver ported from cpp/main.cpp (SPEC-0003, SPEC-0005, SPEC-0006)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Piece
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution


@dataclass(frozen=True)
class SolveResult:
    solution: Solution | None
    start_piece: str | None
    moves: int


class Solver:
    def __init__(self, puzzle: Puzzle) -> None:
        self.pieces = puzzle.piece_set
        self.border = puzzle.border
        self.board = Board(puzzle.border)
        self.used: set[str] = set()
        self.moves = 0

    def solve(
        self,
        start_pieces: Sequence[str] | None = None,
        on_start: Callable[[str], None] | None = None,
    ) -> SolveResult:
        """Find the first solution, trying each start piece at (0, 0) in C++ order (N to A).

        `start_pieces` limits which pieces are tried at (0, 0); the search after that is unchanged.
        A failed start backtracks fully, so the next start begins on an empty board.
        """
        self.board = Board(self.border)
        self.used.clear()
        self.moves = 0
        for piece in self.pieces.search_order:
            if start_pieces is not None and piece.letter not in start_pieces:
                continue
            if on_start:
                on_start(piece.letter)
            if self._try_piece(piece, 0, 0):
                return SolveResult(Solution(grid=self.board.grid()), piece.letter, self.moves)
        return SolveResult(None, None, self.moves)

    def _try_piece(self, piece: Piece, row: int, col: int) -> bool:
        """Place `piece` on (row, col) and recurse (C++ CheckFit)."""
        board = self.board
        for placement in piece.placements:
            if not board.fits(placement, row, col):
                continue
            board.place(piece.letter, placement, row, col)
            self.used.add(piece.letter)
            self.moves += 1
            if len(self.used) == len(self.pieces):
                return True
            free = board.first_free()
            if free is not None:
                for nxt in self.pieces.search_order:
                    if nxt.letter not in self.used and self._try_piece(nxt, *free):
                        return True
            board.remove(placement, row, col)
            self.used.discard(piece.letter)
            self.moves += 1
        return False


def solve(
    puzzle: Puzzle,
    start_pieces: Sequence[str] | None = None,
    on_start: Callable[[str], None] | None = None,
) -> SolveResult:
    return Solver(puzzle).solve(start_pieces, on_start)


def check_solution(puzzle: Puzzle, grid: Sequence[str]) -> bool:
    """True if the grid can be built from the puzzle's pieces with every tab fitting."""
    return Board.from_grid(puzzle, grid) is not None
