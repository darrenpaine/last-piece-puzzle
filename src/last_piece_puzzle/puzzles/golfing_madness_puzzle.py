"""Golfing Madness pieces and border, copied from `ResetPiece` and `InitBoard` in cpp/main.cpp."""

from last_piece_puzzle.pieces import Bit, Border, Piece, Tab

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE

# In letter order; the solver tries them N to A, as the C++ list does.
GOLFING_MADNESS_PIECES: tuple[Piece, ...] = (
    Piece(
        "A",
        "Bluehat",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, OUT, NONE),
            Bit(0, 2, IN, NONE, NONE, IN),
            Bit(1, 2, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "B",
        "Purple Pants",
        (
            Bit(0, 0, OUT, OUT, OUT, NONE),
            Bit(0, 1, NONE, NONE, IN, OUT),
            Bit(-1, 1, OUT, OUT, NONE, OUT),
        ),
    ),
    Piece(
        "C",
        "70s Lady and Green Hat",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, OUT, NONE),
            Bit(0, 2, IN, NONE, IN, NONE),
            Bit(0, 3, NONE, NONE, OUT, OUT),
            Bit(-1, 3, IN, IN, NONE, IN),
        ),
    ),
    Piece(
        "D",
        "Redhead in Tweed",
        (
            Bit(0, 0, OUT, OUT, OUT, NONE),
            Bit(0, 1, NONE, NONE, IN, IN),
            Bit(-1, 1, NONE, OUT, NONE, OUT),
            Bit(-2, 1, IN, IN, NONE, NONE),
            Bit(-2, 2, OUT, NONE, OUT, OUT),
        ),
    ),
    Piece(
        "E",
        "Redhead red Pants",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "F",
        "Redhead orange Socks",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, -1, IN, IN, IN, NONE),
            Bit(1, 0, NONE, NONE, OUT, NONE),
            Bit(1, 1, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "G",
        "BumFlag",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, NONE, IN),
            Bit(2, 0, NONE, OUT, NONE, NONE),
            Bit(2, 1, IN, NONE, IN, IN),
            Bit(3, 0, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "H",
        "Yellow Plus Fours",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, NONE),
            Bit(2, 2, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "I",
        "Pink hat pink pants + friend",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, NONE, IN, IN),
            Bit(1, -1, OUT, OUT, NONE, NONE),
            Bit(2, -1, NONE, IN, NONE, IN),
            Bit(3, -1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "J",
        "Yellow Pants",
        (
            Bit(0, 0, OUT, NONE, OUT, OUT),
            Bit(0, -1, IN, IN, NONE, NONE),
            Bit(1, -1, NONE, OUT, NONE, OUT),
            Bit(2, -1, NONE, IN, NONE, IN),
            Bit(3, -1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "K",
        "Many Balls",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, NONE, NONE),
            Bit(1, 1, OUT, NONE, OUT, OUT),
            Bit(2, 0, NONE, OUT, NONE, OUT),
            Bit(3, 0, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "L",
        "French Shirt",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, OUT, NONE),
            Bit(1, 1, IN, NONE, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "M",
        "Far too white head in red pants",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, OUT, NONE),
            Bit(1, 1, IN, NONE, NONE, IN),
            Bit(2, 1, NONE, OUT, NONE, OUT),
            Bit(3, 1, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "N",
        "ZigZag",
        (
            Bit(0, 0, OUT, OUT, OUT, NONE),
            Bit(0, 1, IN, NONE, NONE, IN),
            Bit(1, 1, NONE, OUT, OUT, NONE),
            Bit(1, 2, IN, NONE, NONE, IN),
            Bit(2, 2, NONE, OUT, OUT, OUT),
        ),
    ),
)

# Bottom[6] and Bottom[7] are both IN on purpose: it makes the pieces fit only one way.
GOLFING_MADNESS_BORDER = Border(
    top=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    left=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    right=(OUT, IN, OUT, IN, OUT, IN, OUT, IN),
    bottom=(OUT, IN, OUT, IN, OUT, IN, IN, IN),
)
