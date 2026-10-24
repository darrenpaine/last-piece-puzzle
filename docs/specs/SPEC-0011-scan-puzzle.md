# SPEC-0011: Scan a puzzle from photos

Status: Draft

## Goal
Add other puzzles in the series without typing every tab by hand. A vision model reads photos of the
pieces and the frame and writes a **puzzle sheet**: a short text file listing the border tabs and each
piece's cells, tabs and name. Plain code checks the sheet, solves it, and writes
`src/last_piece_puzzle/puzzles/<key>_puzzle.py` in the same style as `golfing_madness_puzzle.py`.

The model will misread some tabs, so the sheet is something a person can check against the photos and
fix by hand, then run again without calling the model. Everything after the model call is ordinary
code with ordinary tests. Tests use a fake model and make no real calls (PLAN step 10).

## How it works
```
photos ──(vision model)──> sheet.txt ──(parse, check, solve)──> <key>_puzzle.py
                              ^   |
                              └───┘  fix by hand, run again with --sheet
```

### 1. Photos
- One or more photos of all the pieces, picture side up, spread out so they don't touch.
  Rotation doesn't matter (the solver tries all four). Flipping does, so picture side up only.
- One photo of the empty frame, showing the tabs on all four sides.

### 2. The puzzle sheet
A text file, one item per line, `#` starts a comment. Tabs are `I` (inney), `O` (outey) and `-` (no tab:
that side faces another cell of the same piece).

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
- Board size comes from the border: `top` gives the columns, `left` gives the rows.
- Tab order is north, west, south, east, the order of `Bit`'s fields, so the sheet maps straight onto `Bit`.
- Cell offsets are relative to the piece's first cell. Any offsets work, as in the C++ data.
- Letters are given in the sheet. The scanner gives them in the order the pieces are listed, A, B, C, …

### 3. The model call
- `VisionModel` is a `Protocol` with one method, `read(photos: Sequence[Path]) -> str`, which returns
  sheet text. The real one, `ClaudeVisionModel`, sends the photos to the Claude API with a prompt that
  explains the sheet format, and asks for JSON that matches a schema (structured output). The JSON is
  then written out as sheet text, so the model never has to get the text layout right.
- Model `claude-opus-5-5`, adaptive thinking, effort `high`. Reading tabs off a photo is the hard part,
  so this is worth the cost: one call per puzzle.
- The API key comes from the environment (`ANTHROPIC_API_KEY` or an `ant auth login` profile). Nothing is stored.

### 4. Checks, then solve
Each check stops with a message that names the line, piece or side, so it is easy to fix by hand:
1. The sheet parses (line number on error).
2. `Puzzle(...)` accepts it: the SPEC-0006 checks (cell count, connected pieces, `-` exactly on inside sides…).
3. **Tab balance.** Every inside edge pairs one outey with one inney, and every edge on the border
   pairs a piece tab with the opposite border tab. So
   `piece outeys − piece inneys = border inneys − border outeys`.
   One misread tab changes the left side by 2, so this catches most single misreads before a search.
4. **Solve** with DLX (SPEC-0010, well under a second). At least one solution means the sheet is
   very likely right. No solution means some tab or cell is still wrong.

Only after all four pass is the puzzle module written.

## Inputs / Outputs
- New module `src/last_piece_puzzle/scan.py`:
  - `parse_sheet(text: str) -> Puzzle` and `format_sheet(puzzle: Puzzle) -> str`.
    They round-trip: `parse_sheet(format_sheet(p)) == p`.
  - `tab_balance(puzzle: Puzzle) -> int`: 0 when tabs balance.
  - `write_module(puzzle: Puzzle, key: str) -> str`: the source of `<key>_puzzle.py`.
  - `VisionModel` (Protocol) and `ClaudeVisionModel`.
- New script `last-piece-scan` (in `[project.scripts]`):
  - `last-piece-scan KEY PHOTO... ` calls the model, writes `scans/KEY/sheet.txt`, then checks and solves.
  - `last-piece-scan KEY --sheet scans/KEY/sheet.txt` skips the model: check and solve a hand-fixed sheet.
  - On success, writes `src/last_piece_puzzle/puzzles/KEY_puzzle.py` and prints the number of solutions.
    It won't overwrite an existing module unless given `--force`.
- Folder `scans/KEY/`: the photos and `sheet.txt`. Photos are git-ignored; the sheet is committed, as
  the record of how the module was made.

## Dependencies (need approval)
- `anthropic` (Claude Python SDK) as an optional extra: `uv add --optional scan anthropic`. The solver
  itself keeps no runtime dependencies. `scan.py` imports `anthropic` only inside `ClaudeVisionModel`,
  so tests and mypy work without the API being called.
- Possibly `pillow`, to shrink phone photos under the API's image size limit. Left out unless needed.

## Behaviour
- B-0001: `parse_sheet` reads the format above into a `Puzzle`. Bad lines raise `ValueError` with the
  line number: an unknown key, a tab character not in `I O -`, a cell without four tabs, a cell before
  any `piece` line, a border side missing or given twice.
- B-0002: `format_sheet` writes a `Puzzle` as sheet text in the same layout, and the two round-trip.
- B-0003: `tab_balance` returns `piece outeys − piece inneys − (border inneys − border outeys)`, which
  is 0 for a puzzle that can be solved. The scanner stops and reports the count if it isn't 0.
- B-0004: The scanner runs the checks in order (parse, `Puzzle`, tab balance, DLX solve) and writes
  the module only when all pass. With no solution, it says so and keeps the sheet for fixing.
- B-0005: `write_module` produces a module that `puzzles.load(key)` loads to an equal `Puzzle`, passes
  Ruff (lint and format) and mypy, and uses the `IN, OUT, NONE` names like `golfing_madness_puzzle.py`.
- B-0006: The model is only reached through `VisionModel`. Tests pass a fake that returns fixed sheet
  text. No test calls the API.
- B-0007: `ClaudeVisionModel` sends the photos as base64 images with the format prompt, asks for JSON
  that matches the sheet schema, and turns the JSON into sheet text. A refusal, a cut-off answer or
  JSON that does not match raises `ValueError` with the reason; nothing is written.

## Acceptance tests
- AT-0001: `parse_sheet(format_sheet(PUZZLE)) == PUZZLE` for Golfing Madness and the small test
  puzzles (B-0001, B-0002).
- AT-0002: Each bad sheet in B-0001 raises `ValueError` naming its line (B-0001).
- AT-0003: `tab_balance` is 0 for Golfing Madness, and not 0 after flipping any one piece tab or any one
  border tab (B-0003).
- AT-0004: With a fake model returning the Golfing Madness sheet, `last-piece-scan test_key photo.jpg`
  (in a temp folder) writes `sheet.txt` and a module that loads to an equal puzzle and has 5 solutions.
  It does not overwrite an existing module without `--force` (B-0004, B-0005, B-0006).
- AT-0005: With a fake model returning a sheet with one flipped tab, the scanner stops at tab balance and
  writes no module. With a sheet whose tabs balance but which can't be solved, it stops at the solve
  step and writes no module (B-0004).
- AT-0006: `--sheet` runs the same checks without touching the model (the fake raises if called) (B-0006).
- AT-0007: `ClaudeVisionModel`, with the SDK client replaced by a stub: builds one request with every
  photo as an image block, turns valid JSON into sheet text, and raises `ValueError` on a refusal, on
  `max_tokens`, and on JSON that does not match (B-0007).

## Trial (manual, not CI)
Run the real model on photos of Golfing Madness, where the right answer is known, and compare the
sheet with `PUZZLE`, piece by piece, allowing for rotation and different letters. Record how many
pieces and border sides it got right, and the cost of the call. This decides whether the approach is
good enough before scanning a puzzle we don't have data for.

## Out of scope
- Finding piece outlines with classic image processing (OpenCV and so on).
- A UI for fixing sheets. A text editor and `--sheet` are enough.
- Boards that are not rectangles, or pieces that can be flipped.

## Open questions
1. Do you have photos of Golfing Madness for the trial, and which puzzle should be scanned first after it?
2. Is `scans/KEY/` the right home for the sheet, or should it sit next to the module in `puzzles/`?
3. OK to add `anthropic` as an optional `scan` extra, and `pillow` later only if photos are too big?
