"""Depth-first solver ported from cpp/main.cpp (SPEC-0003, SPEC-0005, SPEC-0006, SPEC-0007)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Piece
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


class Solver:
    def __init__(self, puzzle: Puzzle, all_rotations: bool = False) -> None:
        """`all_rotations` tries all 4 rotations of every piece, as the C++ does."""
        self.pieces = puzzle.piece_set
        self.border = puzzle.border
        self.placements = {
            p.letter: p.placements if all_rotations else p.distinct_placements for p in self.pieces
        }
        self.board = Board(puzzle.border)
        self.used: set[str] = set()
        self.moves = 0

    def solve(
        self,
        start_pieces: Sequence[str] | None = None,
        on_start: Callable[[str], None] | None = None,
        on_solution: Callable[[int, FoundSolution], None] | None = None,
    ) -> SolveResult:
        """Find every solution, trying each start piece at (0, 0) in C++ order (N to A).

        `start_pieces` limits which pieces are tried at (0, 0); the search after that is unchanged.
        `on_solution` is called with the number and details of each new distinct solution.
        """
        self.board = Board(self.border)
        self.used.clear()
        self.moves = 0
        self._boards = 0
        self._found: dict[tuple[str, ...], FoundSolution] = {}
        self._on_solution = on_solution
        for piece in self.pieces.search_order:
            if start_pieces is not None and piece.letter not in start_pieces:
                continue
            if on_start:
                on_start(piece.letter)
            self._start = piece.letter
            self._search(piece, 0, 0)
        return SolveResult(tuple(self._found.values()), self._boards, self.moves)

    def _search(self, piece: Piece, row: int, col: int) -> None:
        """Place `piece` on (row, col) and recurse (C++ CheckFit), carrying on past full boards."""
        board = self.board
        for placement in self.placements[piece.letter]:
            if not board.fits(placement, row, col):
                continue
            board.place(piece.letter, placement, row, col)
            self.used.add(piece.letter)
            self.moves += 1
            if len(self.used) == len(self.pieces):
                self._record()
            elif (free := board.first_free()) is not None:
                for nxt in self.pieces.search_order:
                    if nxt.letter not in self.used:
                        self._search(nxt, *free)
            board.remove(placement, row, col)
            self.used.discard(piece.letter)
            self.moves += 1

    def _record(self) -> None:
        """Keep a full board; an equal letter grid is the same solution found again."""
        self._boards += 1
        grid = self.board.grid()
        found = self._found.get(grid)
        if found is not None:
            self._found[grid] = replace(found, times_found=found.times_found + 1)
            return
        found = FoundSolution(Solution(grid=grid), self._start, self.moves)
        self._found[grid] = found
        if self._on_solution:
            self._on_solution(len(self._found), found)


def solve(
    puzzle: Puzzle,
    start_pieces: Sequence[str] | None = None,
    on_start: Callable[[str], None] | None = None,
    on_solution: Callable[[int, FoundSolution], None] | None = None,
    all_rotations: bool = False,
) -> SolveResult:
    return Solver(puzzle, all_rotations).solve(start_pieces, on_start, on_solution)


def check_solution(puzzle: Puzzle, grid: Sequence[str]) -> bool:
    """True if the grid can be built from the puzzle's pieces with every tab fitting."""
    return Board.from_grid(puzzle, grid) is not None
