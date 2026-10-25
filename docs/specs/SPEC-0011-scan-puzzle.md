# SPEC-0011: Scan a puzzle from photos

Status: Reviewed

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

There are three kinds of photo, each with its own sheet.

### 1. Solved sheet: a photo of the solved puzzle (first)
The pieces sit in the frame, touching, as in a finished puzzle. This is the only photo we have of
Golfing Madness: Anton's `photo_of_puzzle.JPG` (from his repo, saved in `scans/golfing_madness/`).
It is 640×480, the cut lines are faint green on green, and the frame shows. The box above the board has
a "last piece" cut-out that is not part of the board; the prompt tells the model to ignore it.
The file is stored sideways with an EXIF orientation tag, so the board may be read rotated. That still
gives a valid puzzle (its solutions are rotated too). The model reads the board cell by cell: which piece covers each cell (from the cut
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

### 2. Piece sheet: photos of loose pieces (Flight of Fancy)
For a puzzle we only have photos of in pieces, as for Flight of Fancy: all pieces picture side up,
spread out, plus the empty frame.
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

### 3. Unsolved sheet: the puzzle as sold (Puzzling Pets)
The puzzle as it comes in the box: every piece but one in the frame, leaving a gap, and the last
piece lying outside the board, where it won't fit the gap as it is. Our Puzzling Pets photo
(`scans/puzzling_pets/puzzling_pets.jpg`, 750×1000, turned upright, frame showing) has a 3-cell
L-shaped gap, and the loose piece (a grey cat, 3 cells) sits in its holder at the top right of the box.

The sheet is a solved sheet with two additions: gap cells are written `.`, and the loose piece has
cell lines under its `piece` line, as in a piece sheet. A piece with cell lines is loose; a piece
without them is on the board.

```
name: Puzzling Pets
piece A: White cat with a red collar
...
piece M: Grey cat                # the loose piece, as it lies in the photo
  0,0 OI-I
  1,0 -IO-
  1,1 I-OO

row: A:IO-- . . B:OI-O ...       # . is a gap cell
row: ...
top:    IOIOIOIO                 # needed wherever a gap cell touches the frame
```

Checks:
1. The solved sheet checks (1 to 4) for the cells with pieces, except that a side facing a gap cell
   is a tab (`I` or `O`) with nothing to pair it with.
2. Where a gap cell touches the frame, the border line for that side must be given: there is no cell
   tab to work it out from.
3. The loose pieces have as many cells as the gap.
4. `Puzzle(...)` accepts the result, with the board pieces cut out of the grid and the loose pieces
   taken from their cell lines.
5. **Tab balance**, as for a piece sheet: the loose piece and the sides around the gap are read only once.
6. **Solve** with DLX. Unlike a solved photo, this is a real check: the puzzle must have a solution,
   and the photographed layout is not one.

### 4. The model call
- `VisionModel` is a `Protocol`: `read(photos: Sequence[Path], kind: SheetKind) -> str` returns sheet
  text. The real one, `ClaudeVisionModel`, sends the photos to the Claude API with a prompt that
  explains the sheet, and asks for JSON that matches a schema (structured output). The JSON is then
  written out as sheet text, so the model never has to get the text layout right.
- Model `claude-opus-5-5`, adaptive thinking, effort `high`: reading tabs off a photo is the hard part,
  and it is one call per puzzle.
- The API key comes from the environment (`ANTHROPIC_API_KEY` or an `ant auth login` profile). Nothing is stored.

### 5. Gemini as a second model
`GeminiVisionModel` is a second `VisionModel`, chosen with `--model gemini`. It sends the same prompts
and asks for JSON matching the same schemas, so everything after the call is unchanged.
- It uses the `google-genai` SDK's Interactions API, as the Gemini docs show it today:
  `client.interactions.create(model=..., input=[image items..., text item], response_format={"type":
  "text", "mime_type": "application/json", "schema": SCHEMAS[kind]})`, and reads `output_text`. Each
  image item is `{"type": "image", "data": <base64>, "mime_type": ...}`. The exact names are checked
  against the installed SDK when coding.
- Model: `gemini-3.1-pro-preview` by default (the most capable Gemini model now, but a preview that
  Google may retire), or any other with `--gemini-model`, e.g. the stable `gemini-3.8-flash`.
- The key comes from `GEMINI_API_KEY`. Google AI Studio's free tier is enough for a few scans.
- Inline requests can be up to 20 MB in total, so the 5 MB per photo limit for Claude also covers Gemini.
- With two models, the same photo can be scanned by each and the two sheets compared: where they
  differ is a likely misread. That is done by hand (`diff`), not by the scanner.

## Inputs / Outputs
- New module `src/last_piece_puzzle/scan.py`:
  - `parse_solved_sheet(text: str) -> SolvedBoard`: the letter grid, piece names, cell tabs and border.
  - `SolvedBoard.to_puzzle() -> Puzzle` and `SolvedBoard.grid -> Solution`.
  - `parse_piece_sheet(text: str) -> Puzzle` and `format_piece_sheet(puzzle: Puzzle) -> str`, which round-trip.
  - `tab_balance(puzzle: Puzzle) -> int`: 0 when tabs balance.
  - `write_module(puzzle: Puzzle, key: str) -> str`: the source of `<key>_puzzle.py`.
  - `VisionModel` (Protocol), `SheetKind` (`Enum`: `SOLVED`, `PIECES`, `UNSOLVED`), `ClaudeVisionModel`
    and `GeminiVisionModel`.
  - `SolvedBoard` also holds gap cells (`None`) and the loose pieces; `parse_solved_sheet` reads both
    solved and unsolved sheets.
- New script `last-piece-scan` (in `[project.scripts]`):
  - `last-piece-scan KEY PHOTO... [--pieces | --unsolved]` calls the model, writes `scans/KEY/sheet.txt`,
    then checks and solves. A solved photo is the default; `--pieces` is for loose pieces, `--unsolved`
    for the puzzle as sold.
  - `--model {claude,gemini}` picks the model (default `claude`); `--gemini-model NAME` overrides the
    Gemini model.
  - `last-piece-scan KEY --sheet scans/KEY/sheet.txt` skips the model: check a hand-fixed sheet (the
    kind is read from the sheet: `row:` lines mean solved or unsolved, and `.` cells or a piece with
    cell lines mean unsolved).
  - On success, writes `scans/KEY/pieces.txt` (piece sheet) and `src/last_piece_puzzle/puzzles/KEY_puzzle.py`,
    and prints the number of solutions. It won't overwrite an existing module unless given `--force`.
- Folder `scans/KEY/`: the photos and sheets. Photos are git-ignored; sheets are committed.

## Dependencies
- `anthropic` (Claude Python SDK) as an optional extra: `uv add --optional scan anthropic` (approved).
- `google-genai` (Gemini Python SDK) in the same `scan` extra (approved), so `uv sync --extra scan`
  installs both. `scan.py` imports it only inside `GeminiVisionModel`. The solver
  keeps no runtime dependencies. `scan.py` imports `anthropic` only inside `ClaudeVisionModel`.
- Possibly `pillow`, to shrink big phone photos or apply the EXIF rotation. Left out unless needed;
  it would need approval.

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
  It never overwrites `sheet.txt` (it may have hand fixes): with photos and an existing sheet it stops
  and suggests `--sheet`. It checks for an existing module before calling the model (added while coding).
- B-0006: `write_module` produces a module that `puzzles.load(key)` loads to an equal `Puzzle`, that
  passes Ruff and mypy, and that uses the `IN, OUT, NONE` names like `golfing_madness_puzzle.py`.
- B-0007: The model is only reached through `VisionModel`. Tests pass a fake that returns fixed sheet
  text. No test calls the API.
- B-0008: `ClaudeVisionModel` sends the photos as base64 images with the prompt for the sheet kind, asks
  for JSON that matches that kind's schema, and turns the JSON into sheet text. A refusal, a cut-off
  answer or JSON that does not match raises `ValueError` with the reason; nothing is written.
- B-0014: `GeminiVisionModel` sends the photos as base64 image items with the prompt for the sheet kind,
  asks for JSON that matches that kind's schema, and turns the JSON into sheet text with the same code as
  `ClaudeVisionModel`. No text, text that is not JSON, or JSON that does not match raises `ValueError`.
- B-0015: `--model gemini` uses `GeminiVisionModel` (with `--gemini-model` if given); `--model claude`,
  the default, uses `ClaudeVisionModel`. A test can still pass any `VisionModel` to `main`.
- B-0009: `parse_solved_sheet` also reads unsolved sheets: `.` cells are gaps, and a piece with cell
  lines is loose. A side facing a gap must be `I` or `O`. It raises `ValueError` when a gap cell touches
  the frame on a side with no border line, when the loose pieces' cell count differs from the gap's,
  and when there are gap cells but no loose piece, or a loose piece but no gap.
- B-0010: `to_puzzle()` gives the board pieces cut out of the grid and the loose pieces from their cell
  lines, in sheet order. `grid` is only for a board with no gaps.
- B-0011: For an unsolved sheet the scanner checks tab balance, then needs at least one DLX solution.
  `--unsolved` asks the model for an unsolved sheet: gap cells and the loose piece with its cells.

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
- AT-0013: `GeminiVisionModel` with the SDK client replaced by a stub: one request with every photo as
  an image item, the prompt and schema for the kind, and the chosen model name; valid JSON gives the same
  sheet text as for Claude; no text, bad JSON and JSON of the wrong shape raise `ValueError`. The CLI
  builds a `GeminiVisionModel` for `--model gemini` and passes `--gemini-model` through (B-0014, B-0015).
- AT-0009: An unsolved sheet made from fixture 1 by taking out one piece (its cells become `.`, and it is
  listed as loose with its cells) parses, and `to_puzzle()` gives a puzzle with the same pieces up to
  rotation, the `PUZZLE` border and the 5 fixture solutions (B-0009, B-0010).
- AT-0010: Bad unsolved sheets raise `ValueError`: a `-` facing a gap, a gap on the frame with no border
  line, a loose piece with the wrong number of cells, a gap with no loose piece (B-0009).
- AT-0011: With a fake model, `--unsolved` asks for `SheetKind.UNSOLVED` and writes the module from the
  AT-0009 sheet; a sheet with one flipped tab on the loose piece stops at tab balance. `ClaudeVisionModel`
  turns unsolved JSON into the same sheet text (B-0011).

## Trial (manual, not CI)
Run the real model on the photo of the solved Golfing Madness, where the answer is known:
- How many cells got the right piece: compare the letter grid with the fixture solutions, allowing for
  different letters and for the board being read rotated (the frame is not symmetric, so the photo
  should match one fixture exactly once turned the right way).
- How many edges clash (check 3), and after `to_puzzle()`, how many pieces and border tabs equal `PUZZLE`.
- The cost of the call.

This decides whether the approach is good enough, and how much hand fixing to expect, before scanning
Puzzling Pets (unsolved) and Flight of Fancy (loose pieces). For those there is no known answer, so the
checks are tab balance and at least one solution.

### Trial result (2026-10-25)
No API key yet, so a fresh Claude Code subagent, which had seen neither the code nor the answer, read
the photo with the same prompt. It also had an upright copy and enlarged, higher-contrast crops, which
the API call would not get. Compared with fixture 1 (the board in the photo):

| What                       | Result                              |
|----------------------------|-------------------------------------|
| Cells with the right piece | 62 / 64 (15 pieces found, not 14)   |
| Tabbed sides right         | 149 / 156                           |
| Frame tabs right           | 31 / 32 (missed bottom column 7)    |
| Edge clashes flagged       | 0                                   |
| Scanner checks             | all passed                          |
| DLX solutions              | 1,614 (the real puzzle has 5)       |

What it shows:
- **Piece outlines read well**; the two wrong cells came from one split piece.
- **The tabs were mostly inferred, not read.** The subagent said it could not read the inside tabs at
  this resolution, so it assumed a checkerboard (cells where row + column is even are all outeys), which
  matched the frame. That guess is almost right: in Golfing Madness only **1** tabbed side breaks the
  checkerboard, the deliberate break at the bottom right (cell (7, 6) south, frame bottom tab 6). The
  subagent found that break but added a false one next to it (cell (7, 7) south, frame bottom tab 7).
- **The checks didn't notice.** A checkerboard always passes the edge check, and a solved photo always
  solves. But the puzzle came out far too easy: 1,614 solutions instead of 5. The deliberate break is
  what makes the puzzle hard, so a large solution count is a strong sign the break was misread.

Follow-ups:
- B-0012: After the checks pass, the scanner lists every tabbed side that breaks the checkerboard (and
  the frame tabs that break it), so a person can check exactly those few places in the photo. It is a
  report, not a failure: other puzzles may use a different pattern.
- B-0013: When there are more than 20 solutions, the scanner still writes the module but warns that the
  series has only a few solutions, so some tab, probably a break in the pattern, is likely misread.
- AT-0012: For the AT-0001 sheet, the report lists the one Golfing Madness break (bottom right) and
  there's no warning. For the trial sheet (`scans/golfing_madness_scan/sheet.txt`, committed as the
  record) it lists the real break and the false one, and warns about 1,614 solutions.

## Out of scope
- Finding piece outlines with classic image processing (OpenCV and so on).
- A UI for fixing sheets. A text editor and `--sheet` are enough.
- Boards that are not rectangles, or pieces that can be flipped.

## Decisions
- The Golfing Madness photo is Anton's `photo_of_puzzle.JPG`, with the frame showing.
- Puzzling Pets is next, from a photo of the puzzle as sold (the unsolved sheet, added after review).
- Flight of Fancy is from a photo of loose pieces with the frame showing (the piece sheet).
- `anthropic` is approved as an optional `scan` extra.
- Gemini is added as a second model option; `google-genai` is approved, in the same `scan` extra.
