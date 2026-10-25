## Last Piece Puzzle Solver

As a Christmas present, many years ago, I received "Puzzling Pets" - a "Last Piece Puzzle", which required re-arranging the puzzle pieces to fit in the grid. It proved fiendishly difficult to solve. Friends, neighbours and acquaintances tried, but none of us could solve it.

An algorithm to solve a series called "Last Piece Puzzle" created by Dugald
Keith in the 1990s and sold by Blue Opal. Indiana University has [archived photos of all the puzzles](https://digitalcollections.iu.edu/collections/p2678p93x?utf8=%E2%9C%93&cq=last+piece&sort=&locale=en).

As I suspected, I was not the only one to be frustrated by these puzzles, and I
found a *brute-force* [algorithm by Anton](https://github.com/capnramses/golfing_madness_puzzle_solver) for the "Golfing Madness" puzzle in the series using a depth-first search which tries to place each piece and backtracks if it gets stuck. I converted the
algorithm to Python, and all credit for this brute-force algorithm goes to him. I made a few small improvements, including finding all solutions. See below for details.

Then I tried an alternative algorithm based on the [Exact Cover 'Algorithm X'](https://en.wikipedia.org/wiki/Exact_cover) by Donald Knuth, which is
often used to solve puzzles such as Sudoku. Instead of the Knuth's '[dancing links](http://arxiv.org/pdf/cs/0011047)' pointers, I used bitsets (for speed) and added constraints coming from the tabs on puzzle pieces. This new algorithm proved to be an efficient and fast way to solve the puzzle.

Finally, I used Claude to help write a way to scan other last piece puzzles in to be solved.

I recorded the design and decisions made in each step in the docs/specs folder. See the detailed [SPECS](./docs/specs/README.md) there. Each spec also details the expected behaviour and the linked tests implemented in the [tests](./tests/) folder.

### Anton's Brute-Force Algorithm: Conversion and improvements

### New Algorithm: Extended 'Exact Cover' algorithm using bitsets
DLX

### Experimental scan for new puzzles
I worked with Claude to create a way to scan in other puzzles in the series, so that the solver can be run on them.

### Set up and run the solver
You need Python 3.14 and [uv](https://docs.astral.sh/uv/). uv installs everything else.

```
git clone https://github.com/darrenpaine/last-piece-puzzle.git
cd last-piece-puzzle
uv sync
```

Run the solver. With no puzzle named, it shows a menu of the puzzles it knows:

```
uv run last-piece-puzzle                    # choose from a menu
uv run last-piece-puzzle golfing_madness    # solve one puzzle by its key
uv run last-piece-puzzle --list             # list the puzzles
```

It prints each solution as a grid of piece letters, a key to the letters, and a final line such as
`5 solutions found in 19469 rows chosen, 0.1 s (Algorithm X).`

Exact cover is the default. The two depth-first searches are still there for comparison:

| Option                | What it runs                                                   |
|-----------------------|----------------------------------------------------------------|
| `--method exactcover` | Exact cover (default): well under a second                     |
| `--method fastsearch` | Fast depth-first search: about a second, with all CPU cores    |
| `--method search`     | The original port of Anton's C++: a few seconds                |
| `--workers N`         | Processes for the depth-first searches (default: all CPU cores) |

Each puzzle is a module in `src/last_piece_puzzle/puzzles/` named `<key>_puzzle.py`. Add a file
there and the solver picks it up.

### Running the scanner and creating a puzzle
The scanner turns a photo of a puzzle into a puzzle module. A vision model, Claude or Gemini, reads
the photo and writes a **sheet**: a short text file that lists the frame's tabs, and the cells, tabs
and picture of each piece. The scanner checks the sheet, solves it, and only then writes the module.

1. Install the scanner's extra packages and set an API key for the model you want to use:

   ```
   uv sync --extra scan
   export ANTHROPIC_API_KEY=...    # for Claude (the default), or
   export GEMINI_API_KEY=...       # for Gemini, with --model gemini
   ```

2. Put the photo in `scans/<key>/` (photos are not committed) and run the scanner. Use the option
   that matches the photo:

   ```
   uv run last-piece-scan puzzling_pets scans/puzzling_pets/puzzling_pets.jpg --unsolved
   ```

   | Photo                                               | Option             |
   |-----------------------------------------------------|--------------------|
   | The puzzle as sold: a gap, and the last piece aside | `--unsolved`       |
   | The puzzle solved, every piece in the frame         | (none)             |
   | The loose pieces and the empty frame                | `--pieces`         |

   Add `--model gemini` to use Gemini instead of Claude. Turn the photo upright first, so the top of
   the board is at the top.

3. The model's sheet is saved as `scans/<key>/sheet.txt`. If a check fails, the scanner says which
   cell or line is wrong, for example `cell (0, 2) E east is O and cell (0, 3) H west is O: touching
   tabs must differ`. Fix the sheet against the photo and check it again. This doesn't call the model:

   ```
   uv run last-piece-scan puzzling_pets --sheet scans/puzzling_pets/sheet.txt
   ```

   The scanner never overwrites `sheet.txt`, because it may hold your fixes. It won't replace an
   existing puzzle module unless you add `--force`.

4. When every check passes, it writes `src/last_piece_puzzle/puzzles/<key>_puzzle.py`, and
   `scans/<key>/pieces.txt` as a record. Then solve it:

   ```
   uv run last-piece-puzzle puzzling_pets
   ```

The checks:
- **Edges.** Where two pieces touch, one tab is an outey and the other an inney. The exception is a
  photo of the puzzle as sold: every puzzle comes with exactly one place where two inneys touch,
  between an edge piece and the frame. The scanner lists it, and warns if it finds a different number.
- **Tab balance.** The outeys and inneys must pair up across the whole puzzle. One misread tab
  throws this out.
- **Solve.** The puzzle must have a solution.
- **Pattern.** The tabs mostly follow a checkerboard, where each cell is all outeys or all inneys.
  The deliberate breaks in that pattern are what make the puzzles hard, and they are where misreads
  matter most, so the scanner lists them for you to check against the photo. It also warns when there
  are more than 20 solutions: the puzzles in this series have only a few.

You can also skip the model and write a sheet by hand. `scans/puzzling_pets/sheet_claude.txt` is an
example.

