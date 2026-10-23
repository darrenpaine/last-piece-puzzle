## Plan

1. Checking the original C++ produces one solution and recording that solution as an initial test case. This is the "Golfing Madness" puzzle.
Done when: the code produces the solution. A test case can check this.

2. Conversion from C++ to Python, handling pointers correctly.
Done when: the code produces the same solution as the C++ code.

3. Checking the C++ solution is produced by the new Python version. Unit test to check this. When running the test, start with the piece that fits the correct solution (to make it faster?). But also check that other solutions do not work.
Done when: a pytest can check that the solution is produced as expected.

4. Refactoring the code to make it class/object oriented. E.g. Board, Pieces, Piece (methods rotate, etc)... Create tests for these.
Done when: unit tests pass, the solution is still produced.

5. Separate out the pieces definition into the @/src/puzzles folder. For example, as this is the "Golfing Madness" puzzle, the pieces will be defined in @/src/puzzles/golfing_madness.py
If not already done, change the tab encoding from numbers to names/constants/objects. 
Done when: all tests pass, piece definitions in the puzzle folder.

6. Updating the code to continue to find all possible solutions after finding the first one.
Done when: all possible start pieces are used and more than one solution is recorded.

7. Investigate updating the code to run solutions in parallel (on separate Boards and piece lists). 
Done when: it works and is shown to be faster.

8. Potentially see if using a GPU could help.

9. Investigate generation of another puzzle piece definition from a photo of another puzzle in the series using AI to identify edges and pieces and name pieces from the images on them.

