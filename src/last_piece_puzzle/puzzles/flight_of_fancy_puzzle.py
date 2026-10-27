"""Flight of Fancy.

Read by `last-piece-scan` from the sheets in `scans/flight_of_fancy/` (SPEC-0011).
"""

from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE

PIECES: tuple[Piece, ...] = (
    Piece(
        "A",
        "Toucan with yellow beak",
        (
            Bit(0, 0, IN, OUT, NONE, NONE),
            Bit(0, 1, OUT, NONE, OUT, OUT),
            Bit(1, 0, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "B",
        "Brown swallow and green bird",
        (
            Bit(0, 1, IN, IN, NONE, IN),
            Bit(1, 1, NONE, OUT, NONE, OUT),
            Bit(2, 0, OUT, OUT, OUT, NONE),
            Bit(2, 1, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "C",
        "Red quetzal and white seabird",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, NONE, IN),
            Bit(2, 0, NONE, OUT, OUT, NONE),
            Bit(2, 1, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "D",
        "Red bird and flying crane",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, IN, NONE),
            Bit(1, 1, OUT, NONE, NONE, OUT),
            Bit(2, 1, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "E",
        "Red heron",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, NONE),
            Bit(0, 2, IN, NONE, IN, IN),
            Bit(1, 1, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "F",
        "Seagull and green hummingbird",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, NONE, NONE),
            Bit(2, 0, NONE, OUT, NONE, OUT),
            Bit(3, 0, NONE, IN, IN, IN),
            Bit(1, 1, OUT, NONE, OUT, OUT),
        ),
    ),
    Piece(
        "G",
        "Red hummingbird and green bird",
        (
            Bit(0, 1, IN, IN, NONE, IN),
            Bit(1, 0, IN, IN, IN, NONE),
            Bit(1, 1, NONE, NONE, NONE, OUT),
            Bit(2, 1, NONE, IN, NONE, IN),
            Bit(3, 1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "H",
        "Parrot, red bird and blue bird",
        (
            Bit(0, 1, OUT, OUT, NONE, OUT),
            Bit(1, 0, OUT, OUT, NONE, NONE),
            Bit(1, 1, NONE, NONE, IN, IN),
            Bit(2, 0, NONE, IN, NONE, IN),
            Bit(3, 0, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "I",
        "Hummingbird and flamingo",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, NONE, OUT),
            Bit(2, 0, NONE, IN, IN, NONE),
            Bit(2, 1, OUT, NONE, NONE, OUT),
            Bit(3, 1, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "J",
        "Long-tailed black bird and toucan",
        (
            Bit(0, 1, OUT, OUT, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, NONE, OUT),
            Bit(3, 0, OUT, OUT, OUT, NONE),
            Bit(3, 1, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "K",
        "Red bird and swallow",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, NONE, OUT),
            Bit(2, 0, NONE, IN, NONE, IN),
            Bit(3, 0, NONE, OUT, OUT, NONE),
            Bit(3, 1, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "L",
        "Red bird and white seabird",
        (
            Bit(0, 1, IN, IN, NONE, NONE),
            Bit(0, 2, OUT, NONE, OUT, OUT),
            Bit(1, 1, NONE, OUT, NONE, OUT),
            Bit(2, 0, OUT, OUT, OUT, NONE),
            Bit(2, 1, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "M",
        "White seabird and red dove",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, NONE),
            Bit(2, 2, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "N",
        "Kingfisher, pelican and yellow bird",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, IN, NONE),
            Bit(1, 1, OUT, NONE, NONE, OUT),
            Bit(2, 1, NONE, IN, IN, NONE),
            Bit(2, 2, OUT, NONE, OUT, OUT),
        ),
    ),
)

BORDER = Border(
    top=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    left=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    right=(OUT, IN, OUT, IN, OUT, IN, OUT, IN),
    bottom=(OUT, IN, OUT, IN, OUT, IN, IN, IN),
)

PUZZLE = Puzzle("Flight of Fancy", PIECES, BORDER)
