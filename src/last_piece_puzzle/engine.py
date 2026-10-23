"""Fast depth-first search: placements checked per cell ahead of time, bitmask board (SPEC-0009).

The search tries the same placements in the same order as the C++ (SPEC-0003, SPEC-0007), so the
moves and solutions are unchanged. Board cells are numbered row-major: `cell = row * cols + col`.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import NamedTuple, Protocol

from last_piece_puzzle.pieces import Placement, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution

# Sides as indexes into a cell's 4 tabs, in `Bit` order.
NORTH, WEST, SOUTH, EAST = range(4)


@dataclass(frozen=True)
class FoundSolution:
    solution: Solution
    start_piece: str
    found_at_move: int
    times_found: int = 1


class SolutionCallback(Protocol):
    """Called with the number (from 1) and details of each new distinct solution."""

    def __call__(self, number: int, found: FoundSolution, /) -> None: ...


class CellTabs(NamedTuple):
    """A cell covered by a candidate, with the tabs of the bit on it as ints."""

    cell: int
    north: int
    west: int
    south: int
    east: int


class Check(NamedTuple):
    """A bit's tab, which must differ from the facing tab of `cell` if that cell is filled."""

    cell: int
    side: int  # the side of `cell` that faces the bit
    tab: int


class Candidate(NamedTuple):
    """A placement anchored at a cell that is on the board and clear of the border tabs."""

    mask: int
    cells: tuple[CellTabs, ...]
    checks: tuple[Check, ...]
    placement_index: int  # into the piece's placements (or distinct placements)


class Candidates:
    """For each cell and each piece in search order, the placements that could fit there."""

    def __init__(self, puzzle: Puzzle, all_rotations: bool = False) -> None:
        self.rows, self.cols = puzzle.rows, puzzle.cols
        self.size = self.rows * self.cols
        self.puzzle = puzzle
        order = puzzle.piece_set.search_order
        self.letters = tuple(p.letter for p in order)
        self.index = {letter: k for k, letter in enumerate(self.letters)}
        # by_cell[cell][k]: the candidates of piece k (search order) anchored at the cell.
        self.by_cell: list[list[tuple[Candidate, ...]]] = []
        for cell in range(self.size):
            row, col = divmod(cell, self.cols)
            per_piece: list[tuple[Candidate, ...]] = []
            for piece in order:
                placements = piece.placements if all_rotations else piece.distinct_placements
                found = (self._candidate(p, row, col, i) for i, p in enumerate(placements))
                per_piece.append(tuple(c for c in found if c is not None))
            self.by_cell.append(per_piece)

    def at(self, row: int, col: int, letter: str) -> tuple[Candidate, ...]:
        return self.by_cell[row * self.cols + col][self.index[letter]]

    def _candidate(self, placement: Placement, row: int, col: int, index: int) -> Candidate | None:
        """None if the placement is off the board or a tab equals the border there."""
        rows, cols, border = self.rows, self.cols, self.puzzle.border
        own: set[tuple[int, int]] = set()
        for bit in placement:
            r, c = row + bit.row, col + bit.col
            if not (0 <= r < rows and 0 <= c < cols) or (
                (r == 0 and border.top[c] is bit.north)
                or (r == rows - 1 and border.bottom[c] is bit.south)
                or (c == 0 and border.left[r] is bit.west)
                or (c == cols - 1 and border.right[r] is bit.east)
            ):
                return None
            own.add((r, c))
        mask = 0
        cells: list[CellTabs] = []
        checks: list[Check] = []
        for bit in placement:
            r, c = row + bit.row, col + bit.col
            cell = r * cols + c
            mask |= 1 << cell
            tabs = (bit.north.value, bit.west.value, bit.south.value, bit.east.value)
            cells.append(CellTabs(cell, *tabs))
            for tab, dr, dc, facing in (
                (bit.north, -1, 0, SOUTH),
                (bit.west, 0, -1, EAST),
                (bit.south, 1, 0, NORTH),
                (bit.east, 0, 1, WEST),
            ):
                nr, nc = r + dr, c + dc
                if tab is Tab.NONE or not (0 <= nr < rows and 0 <= nc < cols) or (nr, nc) in own:
                    continue
                checks.append(Check(nr * cols + nc, facing, tab.value))
        return Candidate(mask, tuple(cells), tuple(checks), index)


class Engine:
    """The search state: occupancy mask, tabs per cell, moves and the solutions found.

    Counting is as `Solver` (SPEC-0007 B-0001): one move for each place and each remove, and a full
    board is recorded, then backtracked. Equal letter grids are one solution found again.
    """

    def __init__(self, candidates: Candidates, on_solution: SolutionCallback | None = None) -> None:
        self.candidates = candidates
        size = candidates.size
        self.occupied = 0
        self.placed = 0
        self.used = [False] * len(candidates.letters)
        self.tabs = [[Tab.NONE.value] * size for _ in range(4)]  # tabs[side][cell]
        self.grid = ["."] * size
        self.moves = 0
        self.boards = 0
        self.found: dict[tuple[str, ...], FoundSolution] = {}
        self.start = ""
        self._on_solution = on_solution

    def first_free(self) -> int:
        """The first empty cell in row-major order (C++ FindFree)."""
        occupied = self.occupied
        return (~occupied & (occupied + 1)).bit_length() - 1

    def search(self, letter: str, cell: int) -> None:
        """Try every candidate of the piece at the cell, searching below each one that fits."""
        k = self.candidates.index[letter]
        self._search(k, self.candidates.by_cell[cell][k])

    def run_path(self, path: Sequence[tuple[str, int]]) -> None:
        """Place a path of (letter, placement index), each at the first free cell, then search.

        The placements before the last are placed without counting moves (SPEC-0008 tasks).
        """
        self.start = path[0][0]
        for letter, index in path[:-1]:
            self.place(letter, index)
        letter, index = path[-1]
        k = self.candidates.index[letter]
        self._search(k, (self._find(k, index),))

    def place(self, letter: str, index: int) -> None:
        """Place a placement at the first free cell, without checking tabs or counting a move."""
        k = self.candidates.index[letter]
        mask, cells, _, _ = self._find(k, index)
        for cell, *tabs in cells:
            for side, tab in enumerate(tabs):
                self.tabs[side][cell] = tab
            self.grid[cell] = letter
        self.occupied |= mask
        self.used[k] = True
        self.placed += 1

    def _find(self, k: int, index: int) -> Candidate:
        for candidate in self.candidates.by_cell[self.first_free()][k]:
            if candidate.placement_index == index:
                return candidate
        raise ValueError(f"placement {index} of {self.candidates.letters[k]} does not fit there")

    def _search(self, first: int, options: tuple[Candidate, ...]) -> None:
        """Try `options` for piece `first` from the current state; the hot loop uses only locals."""
        by_cell = self.candidates.by_cell
        letters = self.candidates.letters
        count = len(letters)
        every = range(count)
        used, grid, record = self.used, self.grid, self._record
        tabs = self.tabs
        north, west, south, east = tabs
        moves = self.moves

        def fill(
            pieces: Sequence[int], row: Sequence[tuple[Candidate, ...]], occupied: int, placed: int
        ) -> None:
            """Try each unused piece of `pieces` with its candidates in `row`, in order."""
            nonlocal moves
            for k in pieces:
                if used[k]:
                    continue
                letter = letters[k]
                for mask, cells, checks, _ in row[k]:
                    if occupied & mask:
                        continue
                    for cell, side, tab in checks:
                        if occupied >> cell & 1 and tabs[side][cell] == tab:
                            break
                    else:
                        for cell, n, w, s, e in cells:
                            north[cell] = n
                            west[cell] = w
                            south[cell] = s
                            east[cell] = e
                            grid[cell] = letter
                        used[k] = True
                        moves += 1
                        now = occupied | mask
                        if placed + 1 == count:
                            record(moves)
                        else:
                            free = (~now & (now + 1)).bit_length() - 1
                            fill(every, by_cell[free], now, placed + 1)
                        used[k] = False
                        moves += 1

        row: list[tuple[Candidate, ...]] = [()] * count
        row[first] = options
        fill((first,), row, self.occupied, self.placed)
        self.moves = moves

    def _record(self, moves: int) -> None:
        """Keep a full board; an equal letter grid is the same solution found again."""
        self.boards += 1
        cols = self.candidates.cols
        line = "".join(self.grid)
        grid = tuple(line[i : i + cols] for i in range(0, len(line), cols))
        found = self.found.get(grid)
        if found is not None:
            self.found[grid] = replace(found, times_found=found.times_found + 1)
            return
        found = FoundSolution(Solution(grid=grid), self.start, moves)
        self.found[grid] = found
        if self._on_solution:
            self._on_solution(len(self.found), found)
