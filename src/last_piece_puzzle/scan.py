"""Scan a puzzle from photos: sheets, checks and the puzzle module (SPEC-0011).

How it works

1. A vision model reads a photo and writes a sheet: plain text that a person can check against the
   photo and fix by hand. Tabs are `I` (inney), `O` (outey) and `-` (no tab: that side faces another
   cell of the same piece), always in the order north, west, south, east, as in `Bit`.

2. A solved sheet comes from a photo of the solved puzzle. It lists every cell of the board: the
   piece covering it and its four tabs, as it lies on the board. Every edge between two cells is
   written twice, once from each side, so the checks can point at the exact cells the model
   misread: touching tabs must differ, and `-` must face the same piece. Each piece is then cut out
   of the grid.

3. A piece sheet comes from photos of loose pieces and the empty frame. It lists the border, then
   each piece's cells and tabs. No edge is written twice, so the checks are tab balance (every edge
   pairs one outey with one inney) and an exact cover solve.

4. An unsolved sheet comes from a photo of the puzzle as sold: a solved sheet with `.` for the gap
   cells, and the last piece, which lies outside the board, listed with its cells. Its edges are
   checked as in a solved sheet; tab balance and an exact cover solve check the rest.

5. `main` runs a model, Claude or Gemini (or reads a hand-fixed sheet with `--sheet`), runs the
   checks, and writes the piece sheet and `puzzles/<key>_puzzle.py` only when they all pass. It then
   lists the tabs that break the checkerboard, where misreads are most likely, and warns when the
   puzzle has more solutions than the puzzles in this series do.
"""

import argparse
import base64
import json
import re
import sys
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, NoReturn, Protocol

from last_piece_puzzle import puzzles, solver
from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle
from last_piece_puzzle.solution import Solution

if TYPE_CHECKING:
    import anthropic
    from google import genai

TAB_CHARS = {Tab.IN: "I", Tab.OUT: "O", Tab.NONE: "-"}
CHAR_TABS = {char: tab for tab, char in TAB_CHARS.items()}
TAB_NAMES = {Tab.IN: "IN", Tab.OUT: "OUT", Tab.NONE: "NONE"}
BORDER_SIDES = ("top", "left", "right", "bottom")
# The four sides of a cell in sheet order, with the offset of the cell each one faces.
# The side facing back is two places on: north <-> south, west <-> east.
CELL_SIDES = (("north", -1, 0), ("west", 0, -1), ("south", 1, 0), ("east", 0, 1))
HEADER = "# Tabs: I inney, O outey, - none (faces the same piece); order north, west, south, east."

PIECE_KEY = re.compile(r"piece ([A-Z])")
CELL_LINE = re.compile(r"(-?\d+),(-?\d+)\s+(\S+)")
PUZZLE_KEY = re.compile(r"[a-z][a-z0-9_]*")

Tabs = tuple[Tab, Tab, Tab, Tab]
SolvedCell = tuple[str, Tabs]  # the piece letter and the cell's four tabs


class SheetKind(Enum):
    SOLVED = "solved"  # a photo of the solved puzzle
    PIECES = "pieces"  # photos of loose pieces and the empty frame
    UNSOLVED = "unsolved"  # a photo of the puzzle as sold: a gap, and the last piece outside


def sheet_kind(text: str) -> SheetKind:
    """A sheet with `row:` lines is solved, or unsolved if it has `.` cells or cell lines; anything
    else is a piece sheet."""
    lines = [line for _, line in _lines(text)]
    rows = [line.removeprefix("row:").split() for line in lines if line.startswith("row:")]
    if not rows:
        return SheetKind.PIECES
    gaps = any("." in row for row in rows) or any(CELL_LINE.fullmatch(line) for line in lines)
    return SheetKind.UNSOLVED if gaps else SheetKind.SOLVED


def bit_tabs(bit: Bit) -> Tabs:
    return (bit.north, bit.west, bit.south, bit.east)


def _lines(text: str) -> Iterator[tuple[int, str]]:
    """Each line with content: its number (from 1) and its text, without comments or blanks."""
    for number, line in enumerate(text.splitlines(), start=1):
        content = line.partition("#")[0].strip()
        if content:
            yield number, content


def _tabs(text: str, where: str, count: int | None = None) -> tuple[Tab, ...]:
    bad = sorted(set(text) - CHAR_TABS.keys())
    if bad:
        raise ValueError(f"{where}: tab {bad[0]!r} is not I, O or -")
    if count is not None and len(text) != count:
        raise ValueError(f"{where}: {text!r} has {len(text)} tabs, expected {count}")
    return tuple(CHAR_TABS[char] for char in text)


def _cell_tabs(text: str, where: str) -> Tabs:
    north, west, south, east = _tabs(text, where, 4)
    return (north, west, south, east)


# Piece sheets


def piece_sheet_text(
    name: str,
    border: Mapping[str, str],
    pieces: Sequence[tuple[str, str, Sequence[tuple[int, int, str]]]],
) -> str:
    """Lay out a piece sheet from plain strings: border tabs, then (letter, name, cells) per piece.

    Nothing is checked, so a model's answer can be written out as it is and fixed by hand.
    """
    lines = [HEADER, f"name: {name}", ""]
    lines += [f"{side + ':':8}{border.get(side, '')}" for side in BORDER_SIDES]
    for letter, piece_name, cells in pieces:
        lines += ["", f"piece {letter}: {piece_name}"]
        lines += [f"  {row},{col} {tabs}" for row, col, tabs in cells]
    return "\n".join(lines) + "\n"


def format_piece_sheet(puzzle: Puzzle) -> str:
    border = puzzle.border
    return piece_sheet_text(
        puzzle.name,
        {side: "".join(TAB_CHARS[t] for t in getattr(border, side)) for side in BORDER_SIDES},
        [
            (
                piece.letter,
                piece.name,
                [(b.row, b.col, "".join(TAB_CHARS[t] for t in bit_tabs(b))) for b in piece.bits],
            )
            for piece in puzzle.pieces
        ],
    )


def parse_piece_sheet(text: str) -> Puzzle:
    """Read a piece sheet; a bad line raises ValueError with its number (B-0003)."""
    name: str | None = None
    border: dict[str, tuple[Tab, ...]] = {}
    pieces: list[tuple[str, str, list[Bit]]] = []
    for number, line in _lines(text):
        where = f"line {number}"
        if cell := CELL_LINE.fullmatch(line):
            if not pieces:
                raise ValueError(f"{where}: a cell before any piece line")
            tabs = _cell_tabs(cell[3], where)
            pieces[-1][2].append(Bit(int(cell[1]), int(cell[2]), *tabs))
            continue
        key, colon, value = (part.strip() for part in line.partition(":"))
        if not colon:
            raise ValueError(f"{where}: cannot read {line!r}")
        if key == "name":
            name = value
        elif key in BORDER_SIDES:
            if key in border:
                raise ValueError(f"{where}: {key} given twice")
            border[key] = _tabs(value, where)
        elif piece := PIECE_KEY.fullmatch(key):
            pieces.append((piece[1], value, []))
        else:
            raise ValueError(f"{where}: unknown key {key!r}")
    if name is None:
        raise ValueError("no name line")
    missing = [side for side in BORDER_SIDES if side not in border]
    if missing:
        raise ValueError(f"no {missing[0]} line")
    for letter, _, bits in pieces:
        if not bits:
            raise ValueError(f"piece {letter} has no cells")
    return Puzzle(
        name,
        tuple(Piece(letter, piece_name, tuple(bits)) for letter, piece_name, bits in pieces),
        Border(**border),
    )


def tab_balance(puzzle: Puzzle) -> int:
    """0 when the tabs can pair up: piece outeys - piece inneys = border inneys - border outeys.

    Every inside edge pairs one outey with one inney, and every border edge pairs a piece tab with
    the opposite border tab. One misread tab moves the result by 2 (B-0004).
    """
    tabs = [tab for piece in puzzle.pieces for bit in piece.bits for tab in bit_tabs(bit)]
    border = [tab for side in BORDER_SIDES for tab in getattr(puzzle.border, side)]
    return tabs.count(Tab.OUT) - tabs.count(Tab.IN) - (border.count(Tab.IN) - border.count(Tab.OUT))


# Solved and unsolved sheets

BoardCell = SolvedCell | None  # None is a gap cell in an unsolved sheet
Cells = tuple[tuple[BoardCell, ...], ...]


@dataclass(frozen=True)
class SolvedBoard:
    """A solved or unsolved sheet that passed its checks: the puzzle as it lies in the photo."""

    name: str
    names: dict[str, str]  # piece letter -> piece name, in sheet order
    cells: Cells  # by row, then column; None for a gap cell
    border: Border
    loose: tuple[Piece, ...] = ()  # pieces outside the board (unsolved sheet)

    @property
    def grid(self) -> Solution:
        """The board as photographed; `.` for a gap cell."""
        return Solution(
            tuple("".join(cell[0] if cell else "." for cell in row) for row in self.cells)
        )

    @property
    def gaps(self) -> list[tuple[int, int]]:
        return [
            (r, c) for r, row in enumerate(self.cells) for c, cell in enumerate(row) if not cell
        ]

    def to_puzzle(self) -> Puzzle:
        """Cut each board piece out of the grid, anchored on its first cell in reading order, and
        add the loose pieces, in sheet order (B-0002, B-0010)."""
        loose = {piece.letter: piece for piece in self.loose}
        pieces: list[Piece] = []
        for letter, piece_name in self.names.items():
            if letter in loose:
                pieces.append(loose[letter])
                continue
            places = [
                (r, c, cell[1])
                for r, row in enumerate(self.cells)
                for c, cell in enumerate(row)
                if cell and cell[0] == letter
            ]
            top, left, _ = places[0]
            bits = tuple(Bit(r - top, c - left, *tabs) for r, c, tabs in places)
            pieces.append(Piece(letter, piece_name, bits))
        return Puzzle(self.name, tuple(pieces), self.border)


def solved_sheet_text(
    name: str,
    names: Sequence[tuple[str, str]],
    rows: Sequence[Sequence[tuple[str, str]]],
    border: Mapping[str, str],
    loose: Mapping[str, Sequence[tuple[int, int, str]]] | None = None,
) -> str:
    """Lay out a solved or unsolved sheet from plain strings: piece names, rows of (letter, tabs)
    with letter `.` for a gap, the border, and the cells of each loose piece by letter.

    Border sides that are missing or empty are left out. Nothing is checked.
    """
    loose = loose or {}
    lines = [HEADER, f"name: {name}"]
    for letter, piece_name in names:
        lines.append(f"piece {letter}: {piece_name}")
        lines += [f"  {row},{col} {tabs}" for row, col, tabs in loose.get(letter, ())]
    lines.append("")
    lines += [
        "row: " + " ".join("." if letter == "." else f"{letter}:{tabs}" for letter, tabs in row)
        for row in rows
    ]
    sides = [f"{side + ':':8}{border[side]}" for side in BORDER_SIDES if border.get(side)]
    if sides:
        lines += ["", *sides]
    return "\n".join(lines) + "\n"


def _chars(tabs: Sequence[Tab]) -> str:
    return "".join(TAB_CHARS[t] for t in tabs)


def format_solved_sheet(board: SolvedBoard) -> str:
    return solved_sheet_text(
        board.name,
        list(board.names.items()),
        [
            [(cell[0], _chars(cell[1])) if cell else (".", "") for cell in row]
            for row in board.cells
        ],
        {side: _chars(getattr(board.border, side)) for side in BORDER_SIDES},
        {p.letter: [(b.row, b.col, _chars(bit_tabs(b))) for b in p.bits] for p in board.loose},
    )


def parse_solved_sheet(text: str) -> SolvedBoard:
    """Read a solved or unsolved sheet and check every edge; errors name the line or cell
    (B-0001, B-0009).

    Cells are named (row, col), counting from 0 at the top left.
    """
    name: str | None = None
    names: dict[str, str] = {}
    loose_bits: dict[str, list[Bit]] = {}
    rows: list[tuple[BoardCell, ...]] = []
    given: dict[str, tuple[Tab, ...]] = {}
    for number, line in _lines(text):
        where = f"line {number}"
        if cell := CELL_LINE.fullmatch(line):  # a cell of the loose piece named just before
            if not names:
                raise ValueError(f"{where}: a cell before any piece line")
            tabs = _cell_tabs(cell[3], where)
            loose_bits.setdefault(list(names)[-1], []).append(
                Bit(int(cell[1]), int(cell[2]), *tabs)
            )
            continue
        key, colon, value = (part.strip() for part in line.partition(":"))
        if not colon:
            raise ValueError(f"{where}: cannot read {line!r}")
        if key == "name":
            name = value
        elif key == "row":
            row = tuple(_board_cell(token, where) for token in value.split())
            if rows and len(row) != len(rows[0]):
                raise ValueError(
                    f"{where}: row has {len(row)} cells, the first row has {len(rows[0])}"
                )
            rows.append(row)
        elif key in BORDER_SIDES:
            if key in given:
                raise ValueError(f"{where}: {key} given twice")
            given[key] = _tabs(value, where)
        elif piece := PIECE_KEY.fullmatch(key):
            if piece[1] in names:
                raise ValueError(f"{where}: piece {piece[1]} given twice")
            names[piece[1]] = value
        else:
            raise ValueError(f"{where}: unknown key {key!r}")
    if name is None:
        raise ValueError("no name line")
    if not rows:
        raise ValueError("no row lines")
    cells = tuple(rows)
    loose = tuple(Piece(letter, names[letter], tuple(bits)) for letter, bits in loose_bits.items())
    _check_letters(cells, names, loose)
    unsolved = bool(loose)  # _check_letters makes sure a gap and loose pieces come together
    _check_edges(cells, unsolved)
    return SolvedBoard(name, names, cells, _border(cells, given, unsolved), loose)


def _board_cell(token: str, where: str) -> BoardCell:
    if token == ".":
        return None
    letter, colon, tabs = token.partition(":")
    if not colon or not re.fullmatch(r"[A-Z]", letter):
        raise ValueError(f"{where}: cannot read cell {token!r}, expected LETTER:tabs or .")
    return letter, _cell_tabs(tabs, f"{where}, cell {token}")


def _check_letters(cells: Cells, names: Mapping[str, str], loose: Sequence[Piece]) -> None:
    """Every board letter has a piece line; loose pieces fill the gap exactly (B-0009)."""
    loose_letters = {piece.letter for piece in loose}
    seen: set[str] = set()
    gap = 0
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            if cell is None:
                gap += 1
                continue
            letter = cell[0]
            if letter not in names:
                raise ValueError(f"cell ({r}, {c}): piece {letter} has no piece line")
            if letter in loose_letters:
                raise ValueError(f"cell ({r}, {c}): piece {letter} is loose but on the board")
            seen.add(letter)
    if gap and not loose:
        raise ValueError(f"{gap} gap cells but no loose piece (a piece line with cell lines)")
    loose_cells = sum(len(piece.bits) for piece in loose)
    if loose and loose_cells != gap:
        raise ValueError(f"the loose pieces have {loose_cells} cells, the gap has {gap}")
    for letter in names:
        if letter not in seen and letter not in loose_letters:
            raise ValueError(f"piece {letter} covers no cells")


def _check_edges(cells: Cells, unsolved: bool = False) -> None:
    """`-` faces the same piece; a tab faces another piece, the gap or the frame; touching tabs
    differ, except that two inneys may touch in a layout as sold (B-0016)."""
    rows, cols = len(cells), len(cells[0])
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            if cell is None:
                continue
            letter, tabs = cell
            for k, (side, dr, dc) in enumerate(CELL_SIDES):
                tab = tabs[k]
                where = f"cell ({r}, {c}) {letter} {side}"
                nr, nc = r + dr, c + dc
                inside = 0 <= nr < rows and 0 <= nc < cols
                neighbour = cells[nr][nc] if inside else None
                if neighbour is None:
                    if tab is Tab.NONE:
                        facing = "the gap" if inside else "the frame"
                        raise ValueError(f"{where}: - faces {facing}, expected I or O")
                    continue
                other, other_tabs = neighbour
                if other == letter:
                    if tab is not Tab.NONE:
                        raise ValueError(
                            f"{where}: {TAB_CHARS[tab]} faces its own piece, expected -"
                        )
                elif tab is Tab.NONE:
                    raise ValueError(f"{where}: - faces piece {other}, expected I or O")
                elif other_tabs[(k + 2) % 4] is tab and not (unsolved and tab is Tab.IN):
                    facing = CELL_SIDES[(k + 2) % 4][0]
                    raise ValueError(
                        f"{where} is {TAB_CHARS[tab]} and cell ({nr}, {nc}) {other} {facing}"
                        f" is {TAB_CHARS[tab]}: touching tabs must differ"
                    )


def _border(cells: Cells, given: Mapping[str, tuple[Tab, ...]], unsolved: bool = False) -> Border:
    """The frame is opposite each edge cell's outer tab; given border lines must agree. An unsolved
    sheet gives the whole frame, which may have an inney against an edge cell's inney (B-0017)."""
    missing = [side for side in BORDER_SIDES if side not in given]
    if unsolved and missing:
        raise ValueError(f"no {missing[0]} line: an unsolved sheet needs the whole frame")
    edges = {
        "top": [(0, c, 0) for c in range(len(cells[0]))],
        "left": [(r, 0, 1) for r in range(len(cells))],
        "right": [(r, len(cells[0]) - 1, 3) for r in range(len(cells))],
        "bottom": [(len(cells) - 1, c, 2) for c in range(len(cells[0]))],
    }
    border: dict[str, tuple[Tab, ...]] = {}
    for side, places in edges.items():
        if side in given and len(given[side]) != len(places):
            raise ValueError(f"{side}: {len(given[side])} tabs, the board has {len(places)}")
        tabs: list[Tab] = []
        for i, (r, c, k) in enumerate(places):
            cell = cells[r][c]
            frame = given[side][i] if side in given else None
            if frame is Tab.NONE:
                raise ValueError(f"{side} tab {i}: the frame can't have -")
            if cell is None:
                if frame is None:
                    raise ValueError(f"{side}: needed, because cell ({r}, {c}) is in the gap")
                tabs.append(frame)
                continue
            outer = cell[1][k]
            if frame is outer and not (unsolved and outer is Tab.IN):
                raise ValueError(
                    f"{side} tab {i} is {TAB_CHARS[outer]} and cell ({r}, {c}) {cell[0]}"
                    f" {CELL_SIDES[k][0]} is {TAB_CHARS[outer]}: touching tabs must differ"
                )
            tabs.append(frame or (Tab.IN if outer is Tab.OUT else Tab.OUT))
        border[side] = tuple(tabs)
    return Border(**border)


# The checkerboard pattern


def pattern_breaks(puzzle: Puzzle, board: SolvedBoard | None = None) -> list[str]:
    """Tabbed sides that break the checkerboard, where each cell is all outeys or all inneys and
    neighbouring cells differ (B-0012).

    Board cells are checked against one pattern for the whole board, and an unsolved sheet's frame
    against the same pattern. Pieces not on a board (a piece sheet, or loose pieces) are each
    checked against their own best pattern, and a piece sheet's frame against its own.
    """
    breaks: list[str] = []
    on_board: set[str] = set()
    if board is not None:
        sides = [
            (r, c, cell[0], k, tab)
            for r, row in enumerate(board.cells)
            for c, cell in enumerate(row)
            if cell
            for k, tab in enumerate(cell[1])
            if tab is not Tab.NONE
        ]
        on_board = {letter for _, _, letter, _, _ in sides}
        phase = _phase([(r + c, tab) for r, c, _, _, tab in sides])
        breaks += [
            f"cell ({r}, {c}) {letter} {CELL_SIDES[k][0]} is {TAB_CHARS[tab]}"
            for r, c, letter, k, tab in sides
            if tab is not _expected(r + c, phase)
        ]
        frame = _frame_sides(puzzle.border, len(board.cells), len(board.cells[0]))
        gaps = set(board.gaps)
        # A solved board's frame is opposite its cells, so it breaks where they do; an unsolved
        # sheet's frame is read on its own (B-0017), so check all of it.
        breaks += [
            f"{side} tab {i}{' (at the gap)' if (r, c) in gaps else ''} is {TAB_CHARS[tab]}"
            for side, i, (r, c), tab in frame
            if board.loose and tab is _expected(r + c, phase)
        ]
    else:
        frame = _frame_sides(puzzle.border, puzzle.rows, puzzle.cols)
        phase = _phase([(r + c + 1, tab) for _, _, (r, c), tab in frame])
        breaks += [
            f"{side} tab {i} is {TAB_CHARS[tab]}"
            for side, i, (r, c), tab in frame
            if tab is not _expected(r + c + 1, phase)
        ]
    for piece in puzzle.pieces:
        if piece.letter in on_board:
            continue
        sides = [
            (b.row, b.col, piece.letter, k, tab)
            for b in piece.bits
            for k, tab in enumerate(bit_tabs(b))
            if tab is not Tab.NONE
        ]
        phase = _phase([(r + c, tab) for r, c, _, _, tab in sides])
        breaks += [
            f"piece {letter} cell {r},{c} {CELL_SIDES[k][0]} is {TAB_CHARS[tab]}"
            for r, c, letter, k, tab in sides
            if tab is not _expected(r + c, phase)
        ]
    return breaks


def _expected(parity: int, phase: int) -> Tab:
    return Tab.OUT if parity % 2 == phase else Tab.IN


def _phase(sides: Sequence[tuple[int, Tab]]) -> int:
    """0 if cells with an even row + column are mostly outeys, else 1."""
    even_out = sum((parity % 2 == 0) == (tab is Tab.OUT) for parity, tab in sides)
    return 0 if 2 * even_out >= len(sides) else 1


def _frame_sides(
    border: Border, rows: int, cols: int
) -> list[tuple[str, int, tuple[int, int], Tab]]:
    """Each frame tab with the board cell it touches."""
    cells = {
        "top": [(0, c) for c in range(cols)],
        "left": [(r, 0) for r in range(rows)],
        "right": [(r, cols - 1) for r in range(rows)],
        "bottom": [(rows - 1, c) for c in range(cols)],
    }
    return [
        (side, i, cell, tab)
        for side in BORDER_SIDES
        for i, (cell, tab) in enumerate(zip(cells[side], getattr(border, side), strict=True))
    ]


def touching_inneys(board: SolvedBoard) -> list[str]:
    """Where two inneys touch in the photographed layout: between cells, or a cell and the frame."""
    cells = board.cells
    rows, cols = len(cells), len(cells[0])
    pairs: list[str] = []
    for side, i, (r, c), frame in _frame_sides(board.border, rows, cols):
        cell = cells[r][c]
        k = {"top": 0, "left": 1, "bottom": 2, "right": 3}[side]
        if cell and frame is Tab.IN and cell[1][k] is Tab.IN:
            pairs.append(f"{side} tab {i} and cell ({r}, {c}) {cell[0]} {CELL_SIDES[k][0]}")
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            for k in (2, 3):  # south and east, so each edge once
                side, dr, dc = CELL_SIDES[k]
                nr, nc = r + dr, c + dc
                other = cells[nr][nc] if nr < rows and nc < cols else None
                if cell and other and cell[1][k] is Tab.IN and other[1][k - 2] is Tab.IN:
                    pairs.append(
                        f"cell ({r}, {c}) {cell[0]} {side} and cell ({nr}, {nc}) {other[0]}"
                        f" {CELL_SIDES[k - 2][0]}"
                    )
    return pairs


# The puzzle module


def _string(text: str) -> str:
    """A Python string literal, quoted the way Ruff formats it."""
    text = text.replace("\\", "\\\\")
    if '"' in text and "'" not in text:
        return f"'{text}'"
    return '"' + text.replace('"', '\\"') + '"'


def _tuple(items: Sequence[str]) -> str:
    return f"({items[0]},)" if len(items) == 1 else f"({', '.join(items)})"


def write_module(puzzle: Puzzle, key: str) -> str:
    """The source of `puzzles/<key>_puzzle.py`, in the style of `golfing_madness_puzzle.py`."""
    lines = [
        f'"""{puzzle.name}.',
        "",
        f"Read by `last-piece-scan` from the sheets in `scans/{key}/` (SPEC-0011).",
        '"""',
        "",
        "from last_piece_puzzle.pieces import Bit, Border, Piece, Tab",
        "from last_piece_puzzle.puzzle import Puzzle",
        "",
        "IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE",
        "",
        "PIECES: tuple[Piece, ...] = (",
    ]
    for piece in puzzle.pieces:
        lines += [
            "    Piece(",
            f"        {_string(piece.letter)},",
            f"        {_string(piece.name)},",
        ]
        lines.append("        (")
        for b in piece.bits:
            tabs = ", ".join(TAB_NAMES[t] for t in bit_tabs(b))
            lines.append(f"            Bit({b.row}, {b.col}, {tabs}),")
        lines += ["        ),", "    ),"]
    lines += [")", "", "BORDER = Border("]
    for side in BORDER_SIDES:
        lines.append(f"    {side}={_tuple([TAB_NAMES[t] for t in getattr(puzzle.border, side)])},")
    lines += [")", "", f"PUZZLE = Puzzle({_string(puzzle.name)}, PIECES, BORDER)"]
    return "\n".join(lines) + "\n"


# The models


class VisionModel(Protocol):
    """Reads photos and returns sheet text (B-0007)."""

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str: ...


MODEL = "claude-opus-5-5"
GEMINI_MODEL = "gemini-3.1-pro-preview"  # a preview: pass another with --gemini-model if it retires
GEMINI_TIMEOUT_SECONDS = 15 * 60  # one request; without it a stalled request waits forever
GEMINI_ATTEMPTS = 3  # tries for a request that times out or loses its connection
GEMINI_RETRY_SECONDS = 30.0  # the wait before a retry, doubling each time
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # Claude's limit for one image; Gemini allows 20 MB a request
MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
TAB_ENUM: dict[str, object] = {"type": "string", "enum": ["I", "O", "-"]}


def _object(properties: Mapping[str, object]) -> dict[str, object]:
    """A JSON schema object with every property required and no others (structured output)."""
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(properties),
        "additionalProperties": False,
    }


def _array(items: object) -> dict[str, object]:
    return {"type": "array", "items": items}


BORDER_SCHEMA = _object(
    {
        side: {
            "type": "string",
            "description": f"the frame's tabs along the {side}, as a string of I and O",
        }
        for side in BORDER_SIDES
    }
)
CELL_TABS: dict[str, object] = {side: TAB_ENUM for side, _, _ in CELL_SIDES}
NAMED = _object({"letter": {"type": "string"}, "name": {"type": "string"}})
WITH_CELLS = _object(
    {
        "letter": {"type": "string"},
        "name": {"type": "string"},
        "cells": _array(
            _object({"row": {"type": "integer"}, "col": {"type": "integer"}, **CELL_TABS})
        ),
    }
)
ROWS = _array(_array(_object({"letter": {"type": "string"}, **CELL_TABS})))
SCHEMAS = {
    SheetKind.SOLVED: _object(
        {"name": {"type": "string"}, "pieces": _array(NAMED), "rows": ROWS, "border": BORDER_SCHEMA}
    ),
    SheetKind.PIECES: _object(
        {"name": {"type": "string"}, "border": BORDER_SCHEMA, "pieces": _array(WITH_CELLS)}
    ),
    SheetKind.UNSOLVED: _object(
        {
            "name": {"type": "string"},
            "pieces": _array(NAMED),
            "loose": _array(WITH_CELLS),
            "rows": ROWS,
            "border": BORDER_SCHEMA,
        }
    ),
}

ABOUT = """\
This is a "Last Piece Puzzle": a rectangular board of square cells (usually 8 by 8) in a frame.
Each piece covers 3 to 5 cells joined edge to edge and has a cartoon picture on it.

Every side of every cell has one of three tabs:
- "O" (outey): a knob sticks out of this cell across that side;
- "I" (inney): a hole is cut into this cell on that side, for a neighbour's knob;
- "-": no tab, because that side faces another cell of the same piece.
Sides are always north (up), west (left), south (down), east (right) as seen in the photo.
The frame has tabs too: where the frame has a knob sticking into the board, its tab is "O";
where it has a hole, "I". The frame is read top and bottom from left to right, left and right
from top to bottom. If the frame does not show, give empty strings.

Name each piece from its picture, in a few words, e.g. "Golfer in red pants". Give the pieces
letters A, B, C, ... Give the puzzle the name printed on the box, if it shows.
Ignore anything outside the board, such as box art or a cut-out for the "last piece".
"""
CELLS_AS_OFFSETS = """\
cells as (row, col) offsets from its first cell (the top cell, leftmost if there are two), rows
counting down and columns to the right, as it lies in the photo, and each cell's four tabs."""
PROMPTS = {
    SheetKind.SOLVED: ABOUT
    + """
The photo shows the puzzle solved, with every piece in the frame. Go through the board cell by
cell, row by row from the top, left to right. For each cell give the letter of the piece covering
it and its four tabs as it lies on the board. Where two pieces touch, one cell has "O" and the
other "I" on the shared side. Inside a piece, the shared sides are "-".
""",
    SheetKind.PIECES: ABOUT
    + f"""
The photos show the pieces loose, picture side up, and the empty frame. For each piece give its
{CELLS_AS_OFFSETS}
""",
    SheetKind.UNSOLVED: ABOUT.replace(
        'Ignore anything outside the board, such as box art or a cut-out for the "last piece".',
        "Ignore the box art.",
    )
    + f"""
The photo shows the puzzle as sold: every piece but one is in the frame, leaving a gap, and the
last piece lies outside the board, where it does not fit the gap as it is. Go through the board
cell by cell, row by row from the top, left to right. For each cell give the letter of the piece
covering it and its four tabs as it lies on the board. For a gap cell give the letter "." and "-"
for its four tabs. A side facing the gap still has its tab ("I" or "O"). Where two pieces touch,
one cell has "O" and the other "I" on the shared side. Inside a piece, the shared sides are "-".
Read the frame's own tabs all the way round; don't work them out from the pieces. As sold, two
outeys never touch, but two inneys can: these puzzles come with one place where an inney on an
edge piece sits against an inney on the frame.

List the pieces on the board under "pieces". List the last piece only under "loose", with its
{CELLS_AS_OFFSETS}
""",
}


def photo_data(photo: Path) -> tuple[str, str]:
    """The photo's media type and its bytes as base64; unsupported or oversized photos raise."""
    media_type = MEDIA_TYPES.get(photo.suffix.lower())
    if media_type is None:
        raise ValueError(f"{photo}: use a JPEG, PNG, GIF or WebP photo")
    data = photo.read_bytes()
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError(f"{photo}: {len(data)} bytes, the limit is {MAX_PHOTO_BYTES}")
    return media_type, base64.standard_b64encode(data).decode("ascii")


class ClaudeVisionModel:
    """Reads the photos with Claude, asking for JSON that matches the sheet's schema (B-0008)."""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self.client = client

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        import anthropic

        if self.client is None:
            self.client = anthropic.Anthropic()
        content: list[anthropic.types.beta.BetaContentBlockParam] = [
            image_block(photo) for photo in photos
        ]
        content.append({"type": "text", "text": PROMPTS[kind]})
        try:
            with self.client.beta.messages.stream(
                model=MODEL,
                max_tokens=64000,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",  # a declined request is retried on another model
                thinking={"type": "adaptive"},
                output_config={
                    "effort": "high",
                    "format": {"type": "json_schema", "schema": SCHEMAS[kind]},
                },
                messages=[{"role": "user", "content": content}],
            ) as stream:
                message = stream.get_final_message()
        except anthropic.APIError as error:
            raise ValueError(f"Claude API error: {error}") from error
        if message.stop_reason == "refusal":
            details = message.stop_details
            raise ValueError(f"the model declined ({details.category if details else 'no reason'})")
        if message.stop_reason == "max_tokens":
            raise ValueError("the answer was cut off (max_tokens)")
        text = next((block.text for block in message.content if block.type == "text"), None)
        return sheet_from_text(text, kind)


def image_block(photo: Path) -> anthropic.types.beta.BetaImageBlockParam:
    media_type, data = photo_data(photo)
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,  # type: ignore[typeddict-item]
            "data": data,
        },
    }


class GeminiVisionModel:
    """Reads the photos with Gemini, asking for JSON that matches the sheet's schema (B-0014)."""

    def __init__(self, client: genai.Client | None = None, model: str = GEMINI_MODEL) -> None:
        self.client = client
        self.model = model

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        from google import genai

        # Not exported: the errors the interactions API raises, which are not genai.errors.APIError.
        from google.genai._gaos.lib import compat_errors

        if self.client is None:
            self.client = genai.Client(  # the key comes from GEMINI_API_KEY
                http_options=genai.types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000)  # ms
            )
        items: list[dict[str, str]] = []
        for photo in photos:
            media_type, data = photo_data(photo)
            items.append({"type": "image", "data": data, "mime_type": media_type})
        items.append({"type": "text", "text": PROMPTS[kind]})
        # The SDK retries 429 and 5xx itself, but not timeouts or lost connections (B-0019).
        for attempt in range(1, GEMINI_ATTEMPTS + 1):
            try:
                interaction = self.client.interactions.create(
                    model=self.model,
                    input=items,
                    response_format={
                        "type": "text",
                        "mime_type": "application/json",
                        "schema": SCHEMAS[kind],
                    },
                )
                break
            except compat_errors.APIConnectionError as error:  # a timeout is one of these
                failed = f"Gemini request failed: {type(error).__name__}: {error}"
                if attempt == GEMINI_ATTEMPTS:
                    raise ValueError(f"{failed} ({attempt} tries)") from error
                wait = GEMINI_RETRY_SECONDS * 2 ** (attempt - 1)
                print(f"{failed}; trying again in {wait:.0f} s", file=sys.stderr, flush=True)
                time.sleep(wait)
            except (genai.errors.APIError, compat_errors.APIError) as error:
                raise ValueError(f"Gemini API error: {error}") from error
        return sheet_from_text(getattr(interaction, "output_text", None), kind)


def sheet_from_text(text: str | None, kind: SheetKind) -> str:
    """Turn a model's JSON answer into sheet text; no text or bad JSON raises ValueError."""
    if not text:
        raise ValueError("the answer has no text")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"the answer is not JSON: {error}") from error
    return sheet_from_json(data, kind)


def sheet_from_json(data: object, kind: SheetKind) -> str:
    """Turn the model's JSON into sheet text; JSON of the wrong shape raises ValueError."""
    answer = _field(data, "answer", dict)
    border = _field(answer.get("border"), "border", dict)
    sides = {side: _field(border.get(side), f"border {side}", str) for side in BORDER_SIDES}
    name = _field(answer.get("name"), "name", str)
    pieces = _field(answer.get("pieces"), "pieces", list)
    if kind is SheetKind.PIECES:
        return piece_sheet_text(name, sides, [_json_piece(item) for item in pieces])
    names = [
        (_field(p.get("letter"), "letter", str), _field(p.get("name"), "name", str))
        for p in (_field(p, "piece", dict) for p in pieces)
    ]
    loose: dict[str, list[tuple[int, int, str]]] = {}
    if kind is SheetKind.UNSOLVED:
        for item in _field(answer.get("loose"), "loose", list):
            letter, piece_name, cells = _json_piece(item)
            names.append((letter, piece_name))
            loose[letter] = cells
    rows = [
        [_json_cell(_field(cell, "cell", dict)) for cell in _field(row, "row", list)]
        for row in _field(answer.get("rows"), "rows", list)
    ]
    return solved_sheet_text(name, names, rows, sides, loose)


def _json_piece(item: object) -> tuple[str, str, list[tuple[int, int, str]]]:
    piece = _field(item, "piece", dict)
    cells = [
        (_field(c.get("row"), "row", int), _field(c.get("col"), "col", int), _json_cell(c)[1])
        for c in (_field(cell, "cell", dict) for cell in _field(piece.get("cells"), "cells", list))
    ]
    return _field(piece.get("letter"), "letter", str), _field(piece.get("name"), "name", str), cells


def _json_cell(cell: Mapping[str, object]) -> tuple[str, str]:
    """The letter (empty if absent) and four tabs of a JSON cell."""
    letter = _field(cell.get("letter", ""), "letter", str)
    tabs = "".join(_field(cell.get(side), side, str) for side, _, _ in CELL_SIDES)
    return letter, tabs


def _field[T](value: object, what: str, kind: type[T]) -> T:
    if not isinstance(value, kind):
        raise ValueError(f"the answer's {what} is not a {kind.__name__}")
    return value


# The command line

MANY_SOLUTIONS = 20  # the puzzles in the series have only a few (B-0013)
HEARTBEAT_SECONDS = 60.0


class Progress:
    """Timed progress lines on stderr, so a long scan shows where it is (B-0018)."""

    def __init__(self) -> None:
        self.started = time.monotonic()

    def log(self, message: str) -> None:
        seconds = int(time.monotonic() - self.started)
        hours, rest = divmod(seconds, 3600)
        clock = f"{hours}:{rest // 60:02}:{rest % 60:02}"
        print(f"[{clock}] {message}", file=sys.stderr, flush=True)

    @contextmanager
    def waiting(
        self,
        what: str,
        status: Callable[[], str] | None = None,
        every: float = HEARTBEAT_SECONDS,
    ) -> Iterator[None]:
        """Log a "still waiting" line every `every` seconds until the block ends."""
        done = threading.Event()

        def beat() -> None:
            while not done.wait(every):
                self.log(f"Still waiting for {what}" + (f" ({status()})" if status else ""))

        thread = threading.Thread(target=beat, daemon=True)
        thread.start()
        try:
            yield
        finally:
            done.set()
            thread.join()


def check_sheet(text: str) -> tuple[Puzzle, SolvedBoard | None]:
    """Run the checks for the sheet's kind, and return the puzzle and, for a solved or unsolved
    sheet, the board as photographed."""
    if sheet_kind(text) is SheetKind.PIECES:
        puzzle = parse_piece_sheet(text)
        board = None
    else:
        board = parse_solved_sheet(text)
        puzzle = board.to_puzzle()
        if not board.loose:
            return puzzle, board  # a solved photo: every edge was read twice
    if balance := tab_balance(puzzle):
        raise ValueError(f"tabs don't balance (off by {balance}): at least one tab is misread")
    return puzzle, board


def main(
    argv: Sequence[str] | None = None,
    model: VisionModel | None = None,
    puzzles_dir: Path | None = None,
) -> None:
    """Read photos (or a hand-fixed sheet), check the sheet, and write the puzzle module."""
    parser = argparse.ArgumentParser(
        prog="last-piece-scan",
        description="Make a puzzle module from photos of a Last Piece Puzzle.",
    )
    parser.add_argument("key", help="the puzzle's key, e.g. puzzling_pets")
    parser.add_argument("photos", nargs="*", type=Path, help="photos to read")
    kinds = parser.add_mutually_exclusive_group()
    kinds.add_argument("--pieces", action="store_true", help="the photos show loose pieces")
    kinds.add_argument(
        "--unsolved", action="store_true", help="the photo shows the puzzle as sold, with a gap"
    )
    parser.add_argument("--sheet", type=Path, help="check this sheet instead of reading photos")
    parser.add_argument("--force", action="store_true", help="replace an existing puzzle module")
    parser.add_argument(
        "--model", choices=("claude", "gemini"), default="claude", help="model to read the photos"
    )
    parser.add_argument(
        "--gemini-model", default=GEMINI_MODEL, help=f"Gemini model (default: {GEMINI_MODEL})"
    )
    args = parser.parse_args(argv)
    if not PUZZLE_KEY.fullmatch(args.key):
        parser.error("the key must be lower case letters, digits and _, e.g. puzzling_pets")
    if bool(args.photos) == bool(args.sheet):
        parser.error("give photos, or --sheet, but not both")

    progress = Progress()

    def fail(message: str) -> NoReturn:
        progress.log("Stopped")
        parser.exit(1, f"last-piece-scan: {message}\n")

    module = (puzzles_dir or Path(puzzles.__file__).parent) / f"{args.key}_puzzle.py"
    if module.exists() and not args.force:
        fail(f"{module} exists; use --force to replace it")
    folder = Path("scans") / args.key
    sheet: Path = args.sheet or folder / "sheet.txt"
    if args.sheet:
        text = sheet.read_text()
    else:
        if sheet.exists():
            fail(f"{sheet} exists and may have hand fixes; check it with --sheet {sheet}")
        kind = (
            SheetKind.PIECES
            if args.pieces
            else SheetKind.UNSOLVED
            if args.unsolved
            else SheetKind.SOLVED
        )
        if model is None:
            model = (
                GeminiVisionModel(model=args.gemini_model)
                if args.model == "gemini"
                else ClaudeVisionModel()
            )
        name = args.gemini_model if args.model == "gemini" else MODEL
        count = len(args.photos)
        progress.log(f"Reading {count} photo{'s' * (count != 1)} with {name} ({kind.name.lower()})")
        try:
            with progress.waiting(name):
                text = model.read(args.photos, kind)
        except ValueError as error:
            fail(str(error))
        progress.log(f"{name} answered")
        folder.mkdir(parents=True, exist_ok=True)
        sheet.write_text(text)
        print(f"Wrote {sheet}")
    fix = f"Fix {sheet}, then run: last-piece-scan {args.key} --sheet {sheet}"
    progress.log(f"Checking {sheet}")
    try:
        puzzle, board = check_sheet(text)
    except ValueError as error:
        fail(f"{sheet}: {error}\n{fix}")
    progress.log("Solving (Algorithm X)")
    solved = 0

    def on_solution(number: int, found: solver.FoundSolution, /) -> None:
        nonlocal solved
        solved = number

    with progress.waiting("the solver", lambda: f"{solved} solutions so far"):
        result = solver.solve(puzzle, on_solution=on_solution, method="exactcover")
    progress.log("Solved")
    found = [f.solution.grid for f in result.solutions]
    if not found:
        fail(f"{sheet}: the puzzle has no solution, so some tab or cell is wrong\n{fix}")
    if board is not None and not board.loose and board.grid.grid not in found:
        fail(f"{sheet}: the photographed board is not among the solutions")
    pieces_sheet = folder / "pieces.txt"
    folder.mkdir(parents=True, exist_ok=True)
    pieces_sheet.write_text(format_piece_sheet(puzzle))
    module.write_text(write_module(puzzle, args.key))
    print(f"{len(found)} solutions found.")
    print(f"Wrote {pieces_sheet} and {module}")
    breaks = pattern_breaks(puzzle, board)
    if breaks:
        print(f"Tabs that break the checkerboard ({len(breaks)}); check them in the photo:")
        for line in breaks:
            print(f"  {line}")
    if board is not None and board.loose:
        pairs = touching_inneys(board)
        print("Inneys that touch as sold: " + ("; ".join(pairs) or "none"))
        if len(pairs) != 1 or not pairs[0].startswith(BORDER_SIDES):
            print(
                "Warning: as sold, these puzzles have exactly one pair of touching inneys, on the"
                " frame. Check those tabs, and the frame."
            )
    if len(found) > MANY_SOLUTIONS:
        print(
            f"Warning: {len(found)} solutions, but the puzzles in this series have only a few."
            " Some tab, probably a break in the checkerboard, is likely misread."
        )
