"""The board: placing pieces and checking tabs (SPEC-0005)."""

from collections.abc import Iterable, Sequence

from last_piece_puzzle.pieces import Bit, Border, Piece, PieceSet, Placement, Tab

# A cell holds the letter and the bit placed on it, or None when empty.
Cell = tuple[str, Bit] | None


class Board:
    def __init__(self, border: Border) -> None:
        self.border = border
        self.rows = len(border.left)
        self.cols = len(border.top)
        self._cells: list[list[Cell]] = [[None] * self.cols for _ in range(self.rows)]
        self._filled = 0

    def cell(self, row: int, col: int) -> Cell:
        return self._cells[row][col]

    def fits(self, placement: Placement, row: int, col: int) -> bool:
        """Check bounds, overlap, border tabs and neighbour tabs (C++ Sub1, Sub2, Sub3)."""
        cells, border, rows, cols = self._cells, self.border, self.rows, self.cols
        for bit in placement:
            r, c = row + bit.row, col + bit.col
            if not (0 <= r < rows and 0 <= c < cols) or cells[r][c] is not None:
                return False
            if (
                (r == 0 and border.top[c] is bit.north)
                or (r == rows - 1 and border.bottom[c] is bit.south)
                or (c == 0 and border.left[r] is bit.west)
                or (c == cols - 1 and border.right[r] is bit.east)
            ):
                return False
            if bit.north is not Tab.NONE and r > 0:
                cell = cells[r - 1][c]
                if cell is not None and cell[1].south is bit.north:
                    return False
            if bit.south is not Tab.NONE and r < rows - 1:
                cell = cells[r + 1][c]
                if cell is not None and cell[1].north is bit.south:
                    return False
            if bit.west is not Tab.NONE and c > 0:
                cell = cells[r][c - 1]
                if cell is not None and cell[1].east is bit.west:
                    return False
            if bit.east is not Tab.NONE and c < cols - 1:
                cell = cells[r][c + 1]
                if cell is not None and cell[1].west is bit.east:
                    return False
        return True

    def place(self, letter: str, placement: Placement, row: int, col: int) -> None:
        for bit in placement:
            self._cells[row + bit.row][col + bit.col] = (letter, bit)
        self._filled += len(placement)

    def remove(self, placement: Placement, row: int, col: int) -> None:
        for bit in placement:
            self._cells[row + bit.row][col + bit.col] = None
        self._filled -= len(placement)

    def first_free(self) -> tuple[int, int] | None:
        """The first empty cell in row-major order (C++ FindFree)."""
        for r, line in enumerate(self._cells):
            for c, cell in enumerate(line):
                if cell is None:
                    return r, c
        return None

    def is_full(self) -> bool:
        return self._filled == self.rows * self.cols

    def grid(self) -> tuple[str, ...]:
        return tuple("".join(cell[0] if cell else "." for cell in line) for line in self._cells)

    @classmethod
    def from_grid(
        cls, pieces: Iterable[Piece], border: Border, grid: Sequence[str]
    ) -> Board | None:
        """Rebuild a solved board from a letter grid; None if it is not a valid solution."""
        by_letter = PieceSet(pieces).by_letter
        if len(grid) != len(border.left) or any(len(line) != len(border.top) for line in grid):
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
                for p in by_letter[letter].placements
                if {(row + b.row, col + b.col) for b in p} == cells[letter]
            ]
            if not matches:
                return None
            options.append((letter, row, col, matches))
        board = cls(border)

        def place(i: int) -> bool:
            if i == len(options):
                return True
            letter, row, col, matches = options[i]
            for placement in matches:
                if board.fits(placement, row, col):
                    board.place(letter, placement, row, col)
                    if place(i + 1):
                        return True
                    board.remove(placement, row, col)
            return False

        return board if place(0) else None
