"""Depth-first solver ported from cpp/main.cpp (SPEC-0003)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace

from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.solution import Solution

# A piece's bits for one rotation, shifted so that the anchor bit is at (0, 0).
Placement = tuple[Bit, ...]
# A board cell holds the letter and the bit placed on it, or None when empty.
Cell = tuple[str, Bit] | None
Board = list[list[Cell]]


@dataclass(frozen=True)
class SolveResult:
    solution: Solution | None
    start_piece: str | None
    moves: int


def rotate(bit: Bit) -> Bit:
    """Turn a bit 90 degrees clockwise about the piece origin (C++ RotatePiece)."""
    return Bit(bit.col, -bit.row, north=bit.west, west=bit.south, south=bit.east, east=bit.north)


def orientations(piece: Piece) -> tuple[Placement, ...]:
    """Candidate placements in C++ order: each rotation, then each bit as the anchor."""
    placements: list[Placement] = []
    bits = piece.bits
    for _ in range(4):
        for anchor in bits:
            placements.append(
                tuple(replace(b, row=b.row - anchor.row, col=b.col - anchor.col) for b in bits)
            )
        bits = tuple(rotate(b) for b in bits)
    return tuple(placements)


def empty_board(border: Border) -> Board:
    return [[None] * len(border.top) for _ in border.left]


def set_cells(board: Board, placement: Placement, row: int, col: int, letter: str | None) -> None:
    """Place a piece's bits on the board, or clear them when `letter` is None."""
    for bit in placement:
        board[row + bit.row][col + bit.col] = None if letter is None else (letter, bit)


def fits(board: Board, border: Border, placement: Placement, row: int, col: int) -> bool:
    """Check bounds, overlap, border tabs and neighbour tabs (C++ Sub1, Sub2, Sub3)."""
    rows, cols = len(board), len(board[0])
    for bit in placement:
        r, c = row + bit.row, col + bit.col
        if not (0 <= r < rows and 0 <= c < cols) or board[r][c] is not None:
            return False
        if (
            (r == 0 and border.top[c] is bit.north)
            or (r == rows - 1 and border.bottom[c] is bit.south)
            or (c == 0 and border.left[r] is bit.west)
            or (c == cols - 1 and border.right[r] is bit.east)
        ):
            return False
        if bit.north is not Tab.NONE and r > 0:
            cell = board[r - 1][c]
            if cell is not None and cell[1].south is bit.north:
                return False
        if bit.south is not Tab.NONE and r < rows - 1:
            cell = board[r + 1][c]
            if cell is not None and cell[1].north is bit.south:
                return False
        if bit.west is not Tab.NONE and c > 0:
            cell = board[r][c - 1]
            if cell is not None and cell[1].east is bit.west:
                return False
        if bit.east is not Tab.NONE and c < cols - 1:
            cell = board[r][c + 1]
            if cell is not None and cell[1].west is bit.east:
                return False
    return True


class _Search:
    def __init__(self, pieces: Sequence[Piece], border: Border) -> None:
        # The C++ builds its piece list by pushing to the front, so it tries them in reverse.
        self.order = tuple(reversed(pieces))
        self.placements = {p.letter: orientations(p) for p in pieces}
        self.border = border
        self.board = empty_board(border)
        self.used: set[str] = set()
        self.moves = 0

    def first_free(self) -> tuple[int, int]:
        for r, row in enumerate(self.board):
            for c, cell in enumerate(row):
                if cell is None:
                    return r, c
        raise RuntimeError("board is full")

    def try_piece(self, piece: Piece, row: int, col: int) -> bool:
        """Place `piece` on (row, col) and recurse (C++ CheckFit)."""
        for placement in self.placements[piece.letter]:
            if not fits(self.board, self.border, placement, row, col):
                continue
            set_cells(self.board, placement, row, col, piece.letter)
            self.used.add(piece.letter)
            self.moves += 1
            if len(self.used) == len(self.order):
                return True
            next_row, next_col = self.first_free()
            for nxt in self.order:
                if nxt.letter not in self.used and self.try_piece(nxt, next_row, next_col):
                    return True
            set_cells(self.board, placement, row, col, None)
            self.used.discard(piece.letter)
            self.moves += 1
        return False

    def grid(self) -> tuple[str, ...]:
        return tuple("".join(cell[0] if cell else "." for cell in row) for row in self.board)


def solve(
    pieces: Sequence[Piece],
    border: Border,
    start_pieces: Sequence[str] | None = None,
    on_start: Callable[[str], None] | None = None,
) -> SolveResult:
    """Find the first solution, trying each start piece at (0, 0) in C++ order (N to A).

    `start_pieces` limits which pieces are tried at (0, 0); the search after that is unchanged.
    A failed start backtracks fully, so the next start begins on an empty board.
    """
    search = _Search(pieces, border)
    for piece in search.order:
        if start_pieces is not None and piece.letter not in start_pieces:
            continue
        if on_start:
            on_start(piece.letter)
        if search.try_piece(piece, 0, 0):
            return SolveResult(Solution(grid=search.grid()), piece.letter, search.moves)
    return SolveResult(None, None, search.moves)


def build_board(pieces: Sequence[Piece], border: Border, grid: Sequence[str]) -> Board | None:
    """Rebuild a solved board from a letter grid; None if it is not a valid solution."""
    by_letter = {p.letter: p for p in pieces}
    if len(grid) != len(border.left) or any(len(row) != len(border.top) for row in grid):
        return None
    cells: dict[str, set[tuple[int, int]]] = {}
    for r, line in enumerate(grid):
        for c, letter in enumerate(line):
            cells.setdefault(letter, set()).add((r, c))
    if cells.keys() != by_letter.keys():
        return None
    # Anchor each piece on its first cell (row-major) and keep placements with its exact shape.
    options: list[tuple[str, int, int, list[Placement]]] = []
    for letter in sorted(cells, key=lambda letter: min(cells[letter])):
        row, col = min(cells[letter])
        matches = [
            p
            for p in orientations(by_letter[letter])
            if {(row + b.row, col + b.col) for b in p} == cells[letter]
        ]
        if not matches:
            return None
        options.append((letter, row, col, matches))
    board = empty_board(border)

    def place(i: int) -> bool:
        if i == len(options):
            return True
        letter, row, col, matches = options[i]
        for placement in matches:
            if fits(board, border, placement, row, col):
                set_cells(board, placement, row, col, letter)
                if place(i + 1):
                    return True
                set_cells(board, placement, row, col, None)
        return False

    return board if place(0) else None


def check_solution(pieces: Sequence[Piece], border: Border, grid: Sequence[str]) -> bool:
    """True if the grid can be built from the pieces with every tab fitting."""
    return build_board(pieces, border, grid) is not None
