from last_piece_puzzle import solver
from last_piece_puzzle.puzzles.golfing_madness_puzzle import (
    GOLFING_MADNESS_BORDER,
    GOLFING_MADNESS_PIECES,
)


def main() -> None:
    """Solve Golfing Madness and print the result in the C++ layout."""
    print("Last Piece Puzzle solver: Golfing Madness")
    result = solver.solve(
        GOLFING_MADNESS_PIECES,
        GOLFING_MADNESS_BORDER,
        on_start=lambda letter: print(f"Trying to start puzzle with piece {letter}...", flush=True),
    )
    if result.solution is None:
        print(f"Solution NOT Found in {result.moves} Moves.")
        return
    print(f"Solution FOUND starting with piece {result.start_piece}")
    print(f"\nBoard at Move {result.moves}:")
    for row in result.solution.grid:
        print(" ".join(row))
    print()
    for piece in GOLFING_MADNESS_PIECES:
        print(f"{piece.letter} = {piece.name}")
