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
   pairs one outey with one inney) and a DLX solve.

4. `main` runs the model (or reads a hand-fixed sheet with `--sheet`), runs the checks, and writes
   the piece sheet and `puzzles/<key>_puzzle.py` only when they all pass.
"""

import argparse
import base64
import json
import re
from collections.abc import Iterator, Mapping, Sequence
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


def sheet_kind(text: str) -> SheetKind:
    """A sheet with `row:` lines is a solved sheet; anything else is a piece sheet."""
    solved = any(line.strip().startswith("row:") for line in text.splitlines())
    return SheetKind.SOLVED if solved else SheetKind.PIECES


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


# Solved sheets


@dataclass(frozen=True)
class SolvedBoard:
    """A solved sheet that passed its checks: the puzzle as it lies in the photo."""

    name: str
    names: dict[str, str]  # piece letter -> piece name, in sheet order
    cells: tuple[tuple[SolvedCell, ...], ...]  # by row, then column
    border: Border

    @property
    def grid(self) -> Solution:
        return Solution(tuple("".join(letter for letter, _ in row) for row in self.cells))

    def to_puzzle(self) -> Puzzle:
        """Cut each piece out of the grid, anchored on its first cell in reading order (B-0002)."""
        pieces: list[Piece] = []
        for letter, piece_name in self.names.items():
            places = [
                (r, c, tabs)
                for r, row in enumerate(self.cells)
                for c, (cell_letter, tabs) in enumerate(row)
                if cell_letter == letter
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
) -> str:
    """Lay out a solved sheet from plain strings: piece names, rows of (letter, tabs), border.

    Border sides that are missing or empty are left out. Nothing is checked.
    """
    lines = [HEADER, f"name: {name}"]
    lines += [f"piece {letter}: {piece_name}" for letter, piece_name in names]
    lines.append("")
    lines += ["row: " + " ".join(f"{letter}:{tabs}" for letter, tabs in row) for row in rows]
    sides = [f"{side + ':':8}{border[side]}" for side in BORDER_SIDES if border.get(side)]
    if sides:
        lines += ["", *sides]
    return "\n".join(lines) + "\n"


def format_solved_sheet(board: SolvedBoard) -> str:
    return solved_sheet_text(
        board.name,
        list(board.names.items()),
        [
            [(letter, "".join(TAB_CHARS[t] for t in tabs)) for letter, tabs in row]
            for row in board.cells
        ],
        {side: "".join(TAB_CHARS[t] for t in getattr(board.border, side)) for side in BORDER_SIDES},
    )


def parse_solved_sheet(text: str) -> SolvedBoard:
    """Read a solved sheet and check every edge; errors name the line or cell (B-0001).

    Cells are named (row, col), counting from 0 at the top left.
    """
    name: str | None = None
    names: dict[str, str] = {}
    rows: list[tuple[SolvedCell, ...]] = []
    given: dict[str, tuple[Tab, ...]] = {}
    for number, line in _lines(text):
        where = f"line {number}"
        key, colon, value = (part.strip() for part in line.partition(":"))
        if not colon:
            raise ValueError(f"{where}: cannot read {line!r}")
        if key == "name":
            name = value
        elif key == "row":
            row = tuple(_solved_cell(token, where) for token in value.split())
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
    _check_letters(cells, names)
    _check_edges(cells)
    return SolvedBoard(name, names, cells, _border(cells, given))


def _solved_cell(token: str, where: str) -> SolvedCell:
    letter, colon, tabs = token.partition(":")
    if not colon or not re.fullmatch(r"[A-Z]", letter):
        raise ValueError(f"{where}: cannot read cell {token!r}, expected LETTER:tabs")
    return letter, _cell_tabs(tabs, f"{where}, cell {token}")


def _check_letters(cells: tuple[tuple[SolvedCell, ...], ...], names: Mapping[str, str]) -> None:
    seen: set[str] = set()
    for r, row in enumerate(cells):
        for c, (letter, _) in enumerate(row):
            if letter not in names:
                raise ValueError(f"cell ({r}, {c}): piece {letter} has no piece line")
            seen.add(letter)
    for letter in names:
        if letter not in seen:
            raise ValueError(f"piece {letter} covers no cells")


def _check_edges(cells: tuple[tuple[SolvedCell, ...], ...]) -> None:
    """`-` faces the same piece, a tab faces another piece or the frame, touching tabs differ."""
    rows, cols = len(cells), len(cells[0])
    for r, row in enumerate(cells):
        for c, (letter, tabs) in enumerate(row):
            for k, (side, dr, dc) in enumerate(CELL_SIDES):
                tab = tabs[k]
                where = f"cell ({r}, {c}) {letter} {side}"
                nr, nc = r + dr, c + dc
                if not (0 <= nr < rows and 0 <= nc < cols):
                    if tab is Tab.NONE:
                        raise ValueError(f"{where}: - faces the frame, expected I or O")
                    continue
                other, other_tabs = cells[nr][nc]
                if other == letter:
                    if tab is not Tab.NONE:
                        raise ValueError(
                            f"{where}: {TAB_CHARS[tab]} faces its own piece, expected -"
                        )
                elif tab is Tab.NONE:
                    raise ValueError(f"{where}: - faces piece {other}, expected I or O")
                elif other_tabs[(k + 2) % 4] is tab:
                    facing = CELL_SIDES[(k + 2) % 4][0]
                    raise ValueError(
                        f"{where} is {TAB_CHARS[tab]} and cell ({nr}, {nc}) {other} {facing}"
                        f" is {TAB_CHARS[tab]}: touching tabs must differ"
                    )


def _border(
    cells: tuple[tuple[SolvedCell, ...], ...], given: Mapping[str, tuple[Tab, ...]]
) -> Border:
    """The frame is opposite each edge cell's outer tab; given border lines must agree."""
    edges = {
        "top": [(0, c, 0) for c in range(len(cells[0]))],
        "left": [(r, 0, 1) for r in range(len(cells))],
        "right": [(r, len(cells[0]) - 1, 3) for r in range(len(cells))],
        "bottom": [(len(cells) - 1, c, 2) for c in range(len(cells[0]))],
    }
    border: dict[str, tuple[Tab, ...]] = {}
    for side, places in edges.items():
        outer = [cells[r][c][1][k] for r, c, k in places]
        border[side] = tuple(Tab.IN if tab is Tab.OUT else Tab.OUT for tab in outer)
        if side not in given:
            continue
        if len(given[side]) != len(places):
            raise ValueError(f"{side}: {len(given[side])} tabs, the board has {len(places)}")
        for i, ((r, c, k), tab) in enumerate(zip(places, given[side], strict=True)):
            if tab is Tab.NONE:
                raise ValueError(f"{side} tab {i}: the frame can't have -")
            if tab is outer[i]:
                raise ValueError(
                    f"{side} tab {i} is {TAB_CHARS[tab]} and cell ({r}, {c}) {cells[r][c][0]}"
                    f" {CELL_SIDES[k][0]} is {TAB_CHARS[tab]}: touching tabs must differ"
                )
    return Border(**border)


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


# The model


class VisionModel(Protocol):
    """Reads photos and returns sheet text (B-0007)."""

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str: ...


MODEL = "claude-opus-5-5"
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # the API's limit for one image
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
SCHEMAS = {
    SheetKind.SOLVED: _object(
        {
            "name": {"type": "string"},
            "pieces": {
                "type": "array",
                "items": _object({"letter": {"type": "string"}, "name": {"type": "string"}}),
            },
            "rows": {
                "type": "array",
                "items": {
                    "type": "array",
                    "items": _object({"letter": {"type": "string"}, **CELL_TABS}),
                },
            },
            "border": BORDER_SCHEMA,
        }
    ),
    SheetKind.PIECES: _object(
        {
            "name": {"type": "string"},
            "border": BORDER_SCHEMA,
            "pieces": {
                "type": "array",
                "items": _object(
                    {
                        "letter": {"type": "string"},
                        "name": {"type": "string"},
                        "cells": {
                            "type": "array",
                            "items": _object(
                                {
                                    "row": {"type": "integer"},
                                    "col": {"type": "integer"},
                                    **CELL_TABS,
                                }
                            ),
                        },
                    }
                ),
            },
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
PROMPTS = {
    SheetKind.SOLVED: ABOUT
    + """
The photo shows the puzzle solved, with every piece in the frame. Go through the board cell by
cell, row by row from the top, left to right. For each cell give the letter of the piece covering
it and its four tabs as it lies on the board. Where two pieces touch, one cell has "O" and the
other "I" on the shared side. Inside a piece, the shared sides are "-".
""",
    SheetKind.PIECES: ABOUT
    + """
The photos show the pieces loose, picture side up, and the empty frame. For each piece give its
cells as (row, col) offsets from its first cell (the top cell, leftmost if there are two), rows
counting down and columns to the right, as it lies in the photo, and each cell's four tabs.
""",
}


class ClaudeVisionModel:
    """Reads the photos with Claude, asking for JSON that matches the sheet's schema (B-0008)."""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self.client = client

    def read(self, photos: Sequence[Path], kind: SheetKind, /) -> str:
        if self.client is None:
            import anthropic

            self.client = anthropic.Anthropic()
        content: list[anthropic.types.beta.BetaContentBlockParam] = [
            image_block(photo) for photo in photos
        ]
        content.append({"type": "text", "text": PROMPTS[kind]})
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
        if message.stop_reason == "refusal":
            details = message.stop_details
            raise ValueError(f"the model declined ({details.category if details else 'no reason'})")
        if message.stop_reason == "max_tokens":
            raise ValueError("the answer was cut off (max_tokens)")
        text = next((block.text for block in message.content if block.type == "text"), None)
        if text is None:
            raise ValueError("the answer has no text")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"the answer is not JSON: {error}") from error
        return sheet_from_json(data, kind)


def image_block(photo: Path) -> anthropic.types.beta.BetaImageBlockParam:
    media_type = MEDIA_TYPES.get(photo.suffix.lower())
    if media_type is None:
        raise ValueError(f"{photo}: use a JPEG, PNG, GIF or WebP photo")
    data = photo.read_bytes()
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError(f"{photo}: {len(data)} bytes, the limit is {MAX_PHOTO_BYTES}")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,  # type: ignore[typeddict-item]
            "data": base64.standard_b64encode(data).decode("ascii"),
        },
    }


def sheet_from_json(data: object, kind: SheetKind) -> str:
    """Turn the model's JSON into sheet text; JSON of the wrong shape raises ValueError."""
    answer = _field(data, "answer", dict)
    border = _field(answer.get("border"), "border", dict)
    sides = {side: _field(border.get(side), f"border {side}", str) for side in BORDER_SIDES}
    name = _field(answer.get("name"), "name", str)
    pieces = _field(answer.get("pieces"), "pieces", list)
    if kind is SheetKind.SOLVED:
        names = [
            (_field(p.get("letter"), "letter", str), _field(p.get("name"), "name", str))
            for p in (_field(p, "piece", dict) for p in pieces)
        ]
        rows = [
            [_json_cell(_field(cell, "cell", dict)) for cell in _field(row, "row", list)]
            for row in _field(answer.get("rows"), "rows", list)
        ]
        return solved_sheet_text(name, names, rows, sides)
    listed: list[tuple[str, str, list[tuple[int, int, str]]]] = []
    for item in pieces:
        piece = _field(item, "piece", dict)
        cells = [
            (_field(c.get("row"), "row", int), _field(c.get("col"), "col", int), _json_cell(c)[1])
            for c in (
                _field(cell, "cell", dict) for cell in _field(piece.get("cells"), "cells", list)
            )
        ]
        listed.append(
            (
                _field(piece.get("letter"), "letter", str),
                _field(piece.get("name"), "name", str),
                cells,
            )
        )
    return piece_sheet_text(name, sides, listed)


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


def check_sheet(text: str) -> tuple[Puzzle, Solution | None]:
    """Run the checks for the sheet's kind; the photographed board too, for a solved sheet."""
    if sheet_kind(text) is SheetKind.SOLVED:
        board = parse_solved_sheet(text)
        return board.to_puzzle(), board.grid
    puzzle = parse_piece_sheet(text)
    if balance := tab_balance(puzzle):
        raise ValueError(f"tabs don't balance (off by {balance}): at least one tab is misread")
    return puzzle, None


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
    parser.add_argument("--pieces", action="store_true", help="the photos show loose pieces")
    parser.add_argument("--sheet", type=Path, help="check this sheet instead of reading photos")
    parser.add_argument("--force", action="store_true", help="replace an existing puzzle module")
    args = parser.parse_args(argv)
    if not PUZZLE_KEY.fullmatch(args.key):
        parser.error("the key must be lower case letters, digits and _, e.g. puzzling_pets")
    if bool(args.photos) == bool(args.sheet):
        parser.error("give photos, or --sheet, but not both")

    def fail(message: str) -> NoReturn:
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
        kind = SheetKind.PIECES if args.pieces else SheetKind.SOLVED
        try:
            text = (model or ClaudeVisionModel()).read(args.photos, kind)
        except ValueError as error:
            fail(str(error))
        folder.mkdir(parents=True, exist_ok=True)
        sheet.write_text(text)
        print(f"Wrote {sheet}")
    fix = f"Fix {sheet}, then run: last-piece-scan {args.key} --sheet {sheet}"
    try:
        puzzle, photographed = check_sheet(text)
    except ValueError as error:
        fail(f"{sheet}: {error}\n{fix}")
    result = solver.solve(puzzle, method="dlx")
    found = [f.solution.grid for f in result.solutions]
    if not found:
        fail(f"{sheet}: the puzzle has no solution, so some tab or cell is wrong\n{fix}")
    if photographed is not None and photographed.grid not in found:
        fail(f"{sheet}: the photographed board is not among the solutions")
    pieces_sheet = folder / "pieces.txt"
    folder.mkdir(parents=True, exist_ok=True)
    pieces_sheet.write_text(format_piece_sheet(puzzle))
    module.write_text(write_module(puzzle, args.key))
    print(f"{len(found)} solutions found.")
    print(f"Wrote {pieces_sheet} and {module}")
