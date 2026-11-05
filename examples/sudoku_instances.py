"""
Problem specifications written in the Sudoku Problem DSL (Part II demo inputs).

Each instance is a 4x4 Sudoku (Board + 16 Cell objects) built with
`build_sudoku_board_model`. Grid convention: 0 = empty cell (isGiven=False),
1..4 = given clue (isGiven=True, value=v). Rows/columns/boxes are 0-indexed.

The expected values (M, n, m) are checked against the classical baseline by
`examples/run_examples.py` and `tests/test_examples.py`; they are not used by
the transformations.
"""

from dataclasses import dataclass
from typing import List

from besser.BUML.metamodel.object import ObjectModel

from config.solver_config import SolverConfig
from metamodels.problem_dsl import build_sudoku_board_model


@dataclass(frozen=True)
class Instance:
    name: str
    description: str
    grid: List[List[int]]
    num_solutions: int  # M, from the classical baseline
    shots: int = 1024

    def problem_model(self) -> ObjectModel:
        return build_sudoku_board_model(self.name, [row[:] for row in self.grid])

    def solver_config(self) -> SolverConfig:
        return SolverConfig(
            name=f"{self.name}_config",
            num_solutions=self.num_solutions,
            shots=self.shots,
        )


INSTANCES: List[Instance] = [
    Instance(
        name="tiny",
        description="1 empty cell, checkable by hand: (0,1) must be 2.",
        grid=[
            [1, 0, 3, 4],
            [3, 4, 1, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
        num_solutions=1,
    ),
    Instance(
        name="medium",
        description="3 empty cells with a unique solution; needs given-clue pruning and peer uniqueness.",
        grid=[
            [0, 0, 3, 4],
            [3, 4, 1, 2],
            [0, 1, 4, 3],
            [4, 3, 2, 1],
        ],
        num_solutions=1,
    ),
    Instance(
        name="many",
        description="4 empty cells forming a 2x2 rectangle: two valid completions (M=2).",
        grid=[
            [0, 0, 3, 4],
            [3, 4, 1, 2],
            [0, 0, 4, 3],
            [4, 3, 2, 1],
        ],
        num_solutions=2,
    ),
    Instance(
        name="none",
        description="Unsatisfiable: clues are mutually consistent but cell (0,1) has no legal value (M=0).",
        grid=[
            [1, 0, 3, 4],
            [3, 2, 1, 0],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
        num_solutions=0,
    ),
]
