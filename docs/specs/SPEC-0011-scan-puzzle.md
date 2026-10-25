# SPEC-0011: Scan a puzzle from photos

Status: Draft

## Goal
Add other puzzles in the series without typing every tab by hand. A vision model reads a photo and
writes a **sheet**: a short text file a person can check against the photo and fix by hand. Plain code
checks the sheet, builds the `Puzzle`, solves it, and writes `src/last_piece_puzzle/puzzles/<key>_puzzle.py`
in the same style as `golfing_madness_puzzle.py`.

The model will misread some tabs, so after fixing the sheet by hand you can run again without calling
the model. Everything after the model call is ordinary code with ordinary tests. Tests use a fake model
and make no real calls (PLAN step 10).

## How it works
```
photo ──(vision model)──> sheet.txt ──(parse, check, build Puzzle, solve)──> <key>_puzzle.py
                             ^   |
                             └───┘  fix by hand, run again with --sheet
```

There are two kinds of photo, each with its own sheet.

### 1. Solved sheet: a photo of the solved puzzle (first)
The pieces sit in the frame, touching, as in a finished puzzle. This is the only photo we have of
Golfing Madness. The model reads the board cell by cell: which piece covers each cell (from the cut
lines and the pictures), and the tab on each side of each cell, as it lies on the board.

```
name: Golfing Madness
piece A: Bluehat
piece B: Purple Pants
...
row: E:III- E:O--O D:...      # one line per board row, top to bottom
row: ...                      # each cell is LETTER:tabs, tabs north, west, south, east
top:    IOIOIOIO              # optional: the frame, if it shows in the photo
```
Tabs are `I` (inney), `O` (outey) and `-` (no tab: that side faces another cell of the same piece).
The order north, west, south, east is the order of `Bit`'s fields.

Every edge between two cells is written twice, once from each side. That is the useful part: it lets
the code check the model's reading at each edge and point at the exact cells that disagree.

Checks, each naming the cells or line at fault:
1. The sheet parses: rows the same length, four tabs per cell, every letter has a `piece` line.
2. A side facing a cell of the same piece is `-`; every other side is `I` or `O`.
3. Where two pieces touch, the tabs differ (one `I`, one `O`).
4. Border lines, if given, are opposite each edge cell's outer tab. If not given, the border is
   worked out from those tabs.
5. `Puzzle(...)` accepts the result (SPEC-0006: connected pieces, cell count, …).

Then each piece is cut out of the grid: its cells as offsets from its first cell in reading order, with
their tabs as they lie in the photo (rotation doesn't matter, the solver tries all four). DLX (SPEC-0010)
must find the photographed board among the solutions. That checks the conversion, not the reading: a
puzzle built from a solved photo always has that solution. So the CLI also prints the number of
solutions; the puzzles in this series have only a few.

### 2. Piece sheet: photos of loose pieces (later)
For a puzzle we only have in pieces: all pieces picture side up, spread out, plus the empty frame.
The model lists each piece's cells and tabs.

```
name: Golfing Madness
top:    IOIOIOIO        # left to right
left:   IOIOIOIO        # top to bottom
right:  OIOIOIOI        # top to bottom
bottom: OIOIOIII        # left to right

piece A: Bluehat
  0,0 III-              # row,col  then tabs north, west, south, east
  0,1 O-O-
  0,2 I--I
  1,2 -OOO
```
Here no edge is seen twice, so the checks are:
1. The sheet parses (line number on error), and `Puzzle(...)` accepts it.
2. **Tab balance.** Every inside edge pairs one outey with one inney, and every border edge pairs a
   piece tab with the opposite border tab. So `piece outeys − piece inneys = border inneys − border outeys`
   (Golfing Madness: 2 = 2). One misread tab changes the left side by 2.
3. **Solve** with DLX. At least one solution means the sheet is very likely right.

The piece sheet is also the format the scanner saves after a solved sheet passes, as the record of the
pieces in the module.

### 3. The model call
- `VisionModel` is a `Protocol`: `read(photos: Sequence[Path], kind: SheetKind) -> str` returns sheet
  text. The real one, `ClaudeVisionModel`, sends the photos to the Claude API with a prompt that
  explains the sheet, and asks for JSON that matches a schema (structured output). The JSON is then
  written out as sheet text, so the model never has to get the text layout right.
- Model `claude-opus-5-5`, adaptive thinking, effort `high`: reading tabs off a photo is the hard part,
  and it is one call per puzzle.
- The API key comes from the environment (`ANTHROPIC_API_KEY` or an `ant auth login` profile). Nothing is stored.

## Inputs / Outputs
- New module `src/last_piece_puzzle/scan.py`:
  - `parse_solved_sheet(text: str) -> SolvedBoard`: the letter grid, piece names, cell tabs and border.
  - `SolvedBoard.to_puzzle() -> Puzzle` and `SolvedBoard.grid -> Solution`.
  - `parse_piece_sheet(text: str) -> Puzzle` and `format_piece_sheet(puzzle: Puzzle) -> str`, which round-trip.
  - `tab_balance(puzzle: Puzzle) -> int`: 0 when tabs balance.
  - `write_module(puzzle: Puzzle, key: str) -> str`: the source of `<key>_puzzle.py`.
  - `VisionModel` (Protocol), `SheetKind` (`Enum`: `SOLVED`, `PIECES`) and `ClaudeVisionModel`.
- New script `last-piece-scan` (in `[project.scripts]`):
  - `last-piece-scan KEY PHOTO... [--pieces]` calls the model, writes `scans/KEY/sheet.txt`, then checks
    and solves. A solved photo is the default; `--pieces` is for loose pieces.
  - `last-piece-scan KEY --sheet scans/KEY/sheet.txt` skips the model: check a hand-fixed sheet (the
    kind is read from the sheet: `row:` lines mean solved).
  - On success, writes `scans/KEY/pieces.txt` (piece sheet) and `src/last_piece_puzzle/puzzles/KEY_puzzle.py`,
    and prints the number of solutions. It won't overwrite an existing module unless given `--force`.
- Folder `scans/KEY/`: the photos and sheets. Photos are git-ignored; sheets are committed.

## Dependencies (need approval)
- `anthropic` (Claude Python SDK) as an optional extra: `uv add --optional scan anthropic`. The solver
  keeps no runtime dependencies. `scan.py` imports `anthropic` only inside `ClaudeVisionModel`.
- Possibly `pillow`, to shrink phone photos under the API's image size limit. Left out unless needed.

## Behaviour
- B-0001: `parse_solved_sheet` reads the solved sheet. It raises `ValueError` naming the line or cell
  for: a bad line, rows of different lengths, a cell without four tabs, a letter with no `piece` line,
  a `-` facing another piece or the frame, a tab facing its own piece, two touching tabs that are equal,
  and a given border tab equal to the edge cell's tab next to it.
- B-0002: `SolvedBoard.to_puzzle()` cuts each piece out of the grid (offsets from its first cell in
  reading order, tabs as in the photo). The border comes from the border lines or, if absent, opposite
  the edge cells' outer tabs. DLX on that puzzle finds `SolvedBoard.grid` among its solutions.
- B-0003: `parse_piece_sheet` reads the piece sheet into a `Puzzle`; bad lines raise `ValueError` with the
  line number. `format_piece_sheet` writes it back, and the two round-trip.
- B-0004: `tab_balance` returns `piece outeys − piece inneys − (border inneys − border outeys)`, 0 for a
  puzzle that can be solved. For a piece sheet the scanner stops and reports it if it isn't 0.
- B-0005: The scanner runs the checks for the sheet's kind and writes the module only when all pass,
  else it reports the first failure and keeps the sheet for fixing.
- B-0006: `write_module` produces a module that `puzzles.load(key)` loads to an equal `Puzzle`, that
  passes Ruff and mypy, and that uses the `IN, OUT, NONE` names like `golfing_madness_puzzle.py`.
- B-0007: The model is only reached through `VisionModel`. Tests pass a fake that returns fixed sheet
  text. No test calls the API.
- B-0008: `ClaudeVisionModel` sends the photos as base64 images with the prompt for the sheet kind, asks
  for JSON that matches that kind's schema, and turns the JSON into sheet text. A refusal, a cut-off
  answer or JSON that does not match raises `ValueError` with the reason; nothing is written.

## Acceptance tests
- AT-0001: A solved sheet made from fixture `golfing_madness_solution_1` and `PUZZLE` (a test helper
  writes it) parses, and `to_puzzle()` gives the 14 Golfing Madness pieces, each equal to the
  `PUZZLE` piece up to rotation and offset, and the `PUZZLE` border, with and without border lines.
  DLX finds the 5 fixture solutions (B-0001, B-0002).
- AT-0002: Each bad solved sheet in B-0001 raises `ValueError` naming its cell or line. In particular,
  flipping one tab on one side of an inside edge is reported at that pair of cells (B-0001).
- AT-0003: `parse_piece_sheet(format_piece_sheet(PUZZLE)) == PUZZLE` for Golfing Madness and the small
  test puzzles; bad piece sheets raise `ValueError` with the line number (B-0003).
- AT-0004: `tab_balance` is 0 for Golfing Madness, and not 0 after flipping any one piece tab or any one
  border tab (B-0004).
- AT-0005: With a fake model returning the AT-0001 solved sheet, `last-piece-scan test_key photo.jpg`
  (in a temp folder) writes `sheet.txt`, `pieces.txt` and a module that loads to a puzzle with 5
  solutions. It does not overwrite an existing module without `--force` (B-0005, B-0006, B-0007).
- AT-0006: With a fake model returning a solved sheet with one clashing edge, the scanner stops and
  writes no module. With `--pieces` and a piece sheet with one flipped tab, it stops at tab balance (B-0005).
- AT-0007: `--sheet` runs the same checks without touching the model (the fake raises if called) (B-0007).
- AT-0008: `ClaudeVisionModel`, with the SDK client replaced by a stub: builds one request with every
  photo as an image block, turns valid JSON into sheet text, and raises `ValueError` on a refusal, on
  `max_tokens`, and on JSON that does not match (B-0008).

## Trial (manual, not CI)
Run the real model on the photo of the solved Golfing Madness, where the answer is known:
- How many cells got the right piece: compare the letter grid with the fixture solutions, allowing for
  different letters (the frame is not symmetric, so the photo should match one fixture exactly).
- How many edges clash (check 3), and after `to_puzzle()`, how many pieces and border tabs equal `PUZZLE`.
- The cost of the call.

This decides whether the approach is good enough, and how much hand fixing to expect, before scanning
a puzzle we don't have data for.

## Out of scope
- Finding piece outlines with classic image processing (OpenCV and so on).
- A UI for fixing sheets. A text editor and `--sheet` are enough.
- Boards that are not rectangles, or pieces that can be flipped.

## Open questions
1. Does the frame show in the solved photo (its tabs give check 4)? Can you put the photo in
   `scans/golfing_madness/` so I can look at how readable the tabs are before code is written?
2. Which puzzle should be scanned after Golfing Madness, and is it solved or in pieces?
3. OK to add `anthropic` as an optional `scan` extra, and `pillow` later only if photos are too big?
