"""Depth-first solver ported from cpp/main.cpp (SPEC-0003, SPEC-0005)."""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Border, Piece, PieceSet
from last_piece_puzzle.solution import Solution


@dataclass(frozen=True)
class SolveResult:
    solution: Solution | None
    start_piece: str | None
    moves: int


class Solver:
    def __init__(self, pieces: Iterable[Piece], border: Border) -> None:
        self.pieces = PieceSet(pieces)
        self.border = border
        self.board = Board(border)
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
    pieces: Iterable[Piece],
    border: Border,
    start_pieces: Sequence[str] | None = None,
    on_start: Callable[[str], None] | None = None,
) -> SolveResult:
    return Solver(pieces, border).solve(start_pieces, on_start)


def check_solution(pieces: Iterable[Piece], border: Border, grid: Sequence[str]) -> bool:
    """True if the grid can be built from the pieces with every tab fitting."""
    return Board.from_grid(pieces, border, grid) is not None
