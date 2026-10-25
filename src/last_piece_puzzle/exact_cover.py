"""Exact cover solver: Knuth's Algorithm X on bitsets, with a rule for tabs (SPEC-0010).

How it works

1. The puzzle as a table. An exact cover problem is a table of yes/no marks: choose rows so that
   every column is marked exactly once. There is one column per board cell (64) and one per piece
   (14), so a solution fills every cell once and uses every piece once. There is one row per way a
   piece can sit on the board: each distinct rotation (`Piece.distinct_placements`) at each
   position that is on the board and passes the border tabs. A row marks the cells it covers and
   its own piece's column. Golfing Madness has 1,419 rows; for example "E, rotation 0, top-left
   corner" marks cells (0, 0), (0, 1), (0, 2), (1, 0) and the column "piece E".

2. Tabs. Exact cover knows nothing about tabs, so each row also has a set of clashing rows:
   placements that would touch it on a shared edge with an equal tab (outey against outey, inney
   against inney). They are worked out once, before the search.

3. The search. Pick the column with the fewest rows left, the hardest cell or piece to satisfy; if
   it has none, this branch is a dead end. Try each of its rows in turn. Choosing a row removes
   every row that shares a column with it (they would overlap it or reuse its piece), every row
   that clashes with it on tabs, and its own columns. Repeat on what is left; when no columns are
   left, every cell and piece is covered and all tabs fit, so it is a solution. Unlike the
   depth-first search, which always fills the next empty cell in reading order, this works on
   whatever is most constrained and drops options as soon as they become impossible, so dead ends
   show up after one or two choices: about 19,500 rows chosen against about 715,000 placements.

4. Bitsets. Every set of rows is a Python int used as a bitset (bit i = row i): each column's rows,
   each row's `excludes` (shared columns plus tab clashes), and the rows still possible, `alive`.
   Choosing a row is then `alive & ~excludes[row]`, and counting a column's rows left is
   `(columns[k] & alive).bit_count()`; both run in C inside Python.

   This is not dancing links (DLX), Knuth's usual way to run Algorithm X: circular doubly linked
   lists, where covering a column unlinks its nodes and backtracking relinks them. Here the table is
   small (1,419 rows by 78 columns), so each set fits in one int and one C-level AND replaces many
   Python-level pointer updates. Undo is free: `alive` is an int, each call gets its own, and
   returning from the call is the undo.
"""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from last_piece_puzzle.board import Board
from last_piece_puzzle.pieces import Placement, Tab
from last_piece_puzzle.puzzle import SIDES, Puzzle
from last_piece_puzzle.solution import Solution
from last_piece_puzzle.solver import (
    FoundSolution,
    SolutionCallback,
    Solver,
    SolveResult,
    StartCallback,
)

# The side of the neighbouring cell that faces each side of a bit.
FACING = {"north": "south", "south": "north", "west": "east", "east": "west"}


@dataclass(frozen=True)
class CoverRow:
    """One way a piece can sit on the board, anchored on its first cell in reading order."""

    letter: str
    index: int  # position of `placement` in the piece's distinct_placements
    placement: Placement
    row: int
    col: int

    @property
    def cells(self) -> tuple[tuple[int, int], ...]:
        return tuple((self.row + b.row, self.col + b.col) for b in self.placement)


def bits(mask: int) -> Iterator[int]:
    """The positions of the set bits of `mask`, lowest first."""
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


class CoverTable:
    """The exact cover table of a puzzle: rows, column bitsets and each row's `excludes`."""

    def __init__(self, puzzle: Puzzle) -> None:
        """Build the table in three passes: the rows, then the columns, then each row's excludes.

        Every set is one Python int: bit i is set when row i (or column i) is in the set.
        - rows         every way a piece can sit on the board (`CoverRow`), in piece search order
        - columns[k]   the rows that cover column k: a board cell, or a piece
        - covers[i]    the columns that row i covers: its cells and its piece
        - excludes[i]  the rows that can't go with row i: every row sharing a column with it
                       (itself too), plus the rows that clash with it on tabs
        """
        rows, cols = puzzle.rows, puzzle.cols
        board = Board(puzzle.border)  # empty: `fits` checks bounds and border tabs only

        # Pass 1: the rows. Each distinct rotation appears once per bit, with that bit as the
        # anchor (offset (0, 0)). Keep only the one anchored on its first cell in reading order,
        # so each placement gives one row, then try it at every cell (r, c) of the board.
        # `fits` drops positions that run off the board or put a tab against a matching border.
        self.rows: tuple[CoverRow, ...] = tuple(
            CoverRow(piece.letter, index, placement, r, c)
            for piece in puzzle.piece_set.search_order
            for index, placement in enumerate(piece.distinct_placements)
            if min((b.row, b.col) for b in placement) == (0, 0)
            for r in range(rows)
            for c in range(cols)
            if board.fits(placement, r, c)
        )
        # Pass 2: the columns. Columns: the cells in reading order (cell (r, c) is column
        # r * cols + c), then the pieces in definition order. `letters` maps a piece to its column.
        letters = {piece.letter: rows * cols + k for k, piece in enumerate(puzzle.pieces)}
        self.columns: list[int] = [0] * (rows * cols + len(letters))
        self.covers: list[int] = []  # each row's columns, as a bitset over columns
        sides: dict[tuple[int, int, str, Tab], int] = {}  # rows with that tab on that cell side
        for i, cover_row in enumerate(self.rows):
            # The columns row i marks: the cells it covers and its piece.
            marked = [r * cols + c for r, c in cover_row.cells] + [letters[cover_row.letter]]
            for k in marked:
                self.columns[k] |= 1 << i  # add row i to each column it marks
            self.covers.append(sum(1 << k for k in marked))
            # Record row i under every (cell, side, tab) it has, for the tab clashes in pass 3.
            for (r, c), bit in zip(cover_row.cells, cover_row.placement, strict=True):
                for side, _, _ in SIDES:
                    key = (r, c, side, getattr(bit, side))
                    sides[key] = sides.get(key, 0) | 1 << i

        # Pass 3: each row's excludes, worked out once so the search only has to mask them off.
        self.excludes: list[int] = []
        for i, cover_row in enumerate(self.rows):
            # Rows sharing a column with row i: they overlap a cell or use the same piece.
            mask = 0
            for k in bits(self.covers[i]):
                mask |= self.columns[k]
            # Rows clashing on tabs: for each outside side of row i, look up the rows that put
            # the same tab on the facing side of the neighbouring cell (outey on outey, or
            # inney on inney).
            for (r, c), bit in zip(cover_row.cells, cover_row.placement, strict=True):
                for side, dr, dc in SIDES:
                    tab = getattr(bit, side)
                    if tab is not Tab.NONE:  # an outside side: the neighbour must not match it
                        mask |= sides.get((r + dr, c + dc, FACING[side], tab), 0)
            self.excludes.append(mask)


class ExactCoverSolver(Solver):
    """Finds the same solutions as `Solver`, in the same order, by exact cover (SPEC-0010)."""

    def __init__(self, puzzle: Puzzle, all_rotations: bool = False) -> None:
        """`all_rotations` makes no difference: rows are distinct placements (B-0005)."""
        super().__init__(puzzle, all_rotations)
        self.table = CoverTable(puzzle)

    def solve(
        self,
        start_pieces: Sequence[str] | None = None,
        on_start: StartCallback | None = None,
        on_solution: SolutionCallback | None = None,
        workers: int | None = None,
    ) -> SolveResult:
        """Find every solution once; `moves` counts rows chosen. `workers` is ignored (B-0005)."""
        # Every set is one Python int: bit i is set when row i (or column i) is in the set.
        # - columns[k]   the rows that cover column k
        # - covers[i]    the columns that row i covers
        # - excludes[i]  the rows that can't go with row i: every row sharing a column with it
        #                (itself too), plus the rows that clash with it on tabs
        # - alive        the rows still possible; open_columns the columns still to cover
        table = self.table
        columns, covers, excludes = table.columns, table.covers, table.excludes
        starts = self.start_order(start_pieces)
        if on_start:
            for piece in starts:
                on_start(piece.letter)
        allowed = {piece.letter for piece in starts}
        # Start with every row alive, then drop the rows that put a piece not in `starts` on the
        # top-left cell (0, 0), so only the chosen start pieces can begin a solution.
        alive = (1 << len(table.rows)) - 1
        for i in bits(columns[0]):  # the rows covering (0, 0)
            if table.rows[i].letter not in allowed:
                alive &= ~(1 << i)
        chosen: list[int] = []
        found: list[tuple[tuple[int, ...], int]] = []  # rows of each solution, rows chosen so far
        moves = 0

        def search(alive: int, open_columns: int) -> None:
            nonlocal moves
            # Every cell is filled and every piece used: the chosen rows are a solution.
            if not open_columns:
                found.append((tuple(chosen), moves))
                return
            # Find the open column with the fewest rows left: the hardest cell or piece to place.
            best, fewest = -1, 0
            for k in bits(open_columns):
                # Calculate rows left in column k:
                count = (columns[k] & alive).bit_count()
                if best < 0 or count < fewest:
                    best, fewest = k, count
                    if count == 0:  # nothing can cover it: dead end, back up
                        return
            # Try each row that covers that column, in turn.
            for i in bits(columns[best] & alive):
                # Choosing row i as the next: drop every row it excludes, close the columns it
                # covers, search on, then undo the choice and try the next row.
                moves += 1
                chosen.append(i)
                search(alive & ~excludes[i], open_columns & ~covers[i])
                chosen.pop()

        search(alive, (1 << len(columns)) - 1)  # all columns start open
        # The search finds solutions in its own order; sort them into the order the depth-first
        # search would find them, so the numbering matches `Solver`.
        found.sort(key=lambda item: self._dfs_path(item[0]))
        solutions = tuple(self._found(rows, at) for rows, at in found)
        if on_solution:
            for number, solution in enumerate(solutions, start=1):
                on_solution(number, solution)
        return SolveResult(solutions, len(solutions), moves)

    def _dfs_path(self, rows: Sequence[int]) -> list[tuple[int, int, int, int]]:
        """The path DFS takes to this solution: per free cell, piece rank and placement (B-0002)."""
        rank = {piece.letter: k for k, piece in enumerate(self.pieces.search_order)}
        chosen = [self.table.rows[i] for i in rows]
        return sorted((row.row, row.col, rank[row.letter], row.index) for row in chosen)

    def _found(self, rows: Sequence[int], at: int) -> FoundSolution:
        grid = [["."] * self.puzzle.cols for _ in range(self.puzzle.rows)]
        start = ""
        for i in rows:
            cover_row = self.table.rows[i]
            for r, c in cover_row.cells:
                grid[r][c] = cover_row.letter
            if (cover_row.row, cover_row.col) == (0, 0):
                start = cover_row.letter
        return FoundSolution(Solution(tuple("".join(line) for line in grid)), start, at)
