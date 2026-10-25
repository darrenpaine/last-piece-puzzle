"""Puzzling Pets.

Read by `last-piece-scan` from the sheets in `scans/puzzling_pets/` (SPEC-0011).
"""

from last_piece_puzzle.pieces import Bit, Border, Piece, Tab
from last_piece_puzzle.puzzle import Puzzle

IN, OUT, NONE = Tab.IN, Tab.OUT, Tab.NONE

PIECES: tuple[Piece, ...] = (
    Piece(
        "A",
        "Grey dog, beach ball and upside-down beagle",
        (
            Bit(0, 0, OUT, OUT, OUT, NONE),
            Bit(0, 1, IN, NONE, IN, NONE),
            Bit(0, 2, OUT, NONE, OUT, NONE),
            Bit(0, 3, IN, NONE, NONE, IN),
            Bit(1, 3, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "B",
        "Brown spotted dog and white terrier",
        (
            Bit(0, 0, OUT, OUT, NONE, NONE),
            Bit(0, 1, IN, NONE, IN, NONE),
            Bit(0, 2, OUT, NONE, OUT, NONE),
            Bit(0, 3, IN, NONE, IN, IN),
            Bit(1, 0, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "C",
        "Bull terrier and ginger tabby cat",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, NONE),
            Bit(2, 2, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "D",
        "Tiger-striped cat and lilac kitten",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, OUT, NONE),
            Bit(1, 1, IN, NONE, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "E",
        "Cat with a red tail and red-and-white cat on its back",
        (
            Bit(0, 0, IN, IN, NONE, NONE),
            Bit(0, 1, OUT, NONE, OUT, OUT),
            Bit(1, 0, NONE, OUT, NONE, OUT),
            Bit(2, -1, OUT, OUT, OUT, NONE),
            Bit(2, 0, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "F",
        "Bones and red-and-white dog",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, 0, NONE, IN, NONE, IN),
            Bit(2, 0, NONE, OUT, NONE, NONE),
            Bit(2, 1, IN, NONE, IN, IN),
            Bit(3, 0, NONE, IN, IN, IN),
        ),
    ),
    Piece(
        "G",
        "Siamese cat stretching",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, 0, NONE, OUT, NONE, OUT),
            Bit(2, -1, OUT, OUT, OUT, NONE),
            Bit(2, 0, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "H",
        "Grey hound lying down",
        (
            Bit(0, 0, IN, IN, NONE, IN),
            Bit(1, -1, IN, IN, IN, NONE),
            Bit(1, 0, NONE, NONE, OUT, NONE),
            Bit(1, 1, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "I",
        "Brown tabby cat reaching up and red dog lying down",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, -1, OUT, OUT, NONE, NONE),
            Bit(1, 0, NONE, NONE, IN, IN),
            Bit(2, -2, OUT, OUT, OUT, NONE),
            Bit(2, -1, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "J",
        "Ginger cat and black cat leaping",
        (
            Bit(0, 0, OUT, OUT, OUT, NONE),
            Bit(0, 1, IN, NONE, IN, NONE),
            Bit(0, 2, OUT, NONE, NONE, OUT),
            Bit(1, 2, NONE, IN, IN, NONE),
            Bit(1, 3, OUT, NONE, OUT, OUT),
        ),
    ),
    Piece(
        "K",
        "Beach ball, striped ginger cat and shih tzu",
        (
            Bit(0, 0, IN, IN, IN, NONE),
            Bit(0, 1, OUT, NONE, NONE, OUT),
            Bit(1, 1, NONE, IN, NONE, IN),
            Bit(2, 1, NONE, OUT, OUT, OUT),
        ),
    ),
    Piece(
        "L",
        "White cat with a collar and dachshund",
        (
            Bit(0, 0, OUT, OUT, NONE, NONE),
            Bit(0, 1, IN, NONE, IN, IN),
            Bit(1, -2, IN, IN, IN, NONE),
            Bit(1, -1, OUT, NONE, OUT, NONE),
            Bit(1, 0, NONE, NONE, IN, IN),
        ),
    ),
    Piece(
        "M",
        "Barking dog and black dog",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, -1, OUT, OUT, OUT, NONE),
            Bit(1, 0, NONE, NONE, IN, NONE),
            Bit(1, 1, OUT, NONE, OUT, NONE),
            Bit(1, 2, IN, NONE, IN, IN),
        ),
    ),
    Piece(
        "N",
        "Grey spotted cat (the last piece)",
        (
            Bit(0, 0, OUT, OUT, NONE, OUT),
            Bit(1, -1, OUT, OUT, OUT, NONE),
            Bit(1, 0, NONE, NONE, IN, OUT),
        ),
    ),
)

BORDER = Border(
    top=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    left=(IN, OUT, IN, OUT, IN, OUT, IN, OUT),
    right=(OUT, IN, OUT, IN, OUT, IN, OUT, IN),
    bottom=(OUT, IN, OUT, IN, OUT, IN, IN, IN),
)

PUZZLE = Puzzle("Puzzling Pets", PIECES, BORDER)
