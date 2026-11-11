"""
Classical baselines (`classical_baseline.py`), Lecture T6, Slides 18-19, 22.

1. `solve_sudoku_brute_force(problem_model)`: every valid completion of the Sudoku, by trying
   all values in the empty cells. Deliberately independent of the SAT encoding, so it can
   serve as the reference for T1 (and later for the quantum results).
2. `solve_sat_brute_force(solution_model)`: every satisfying assignment `{var_id: bool}` of the
   CNF formula, enumerated with the Glucose SAT solver from PySAT (Ignatiev et al., 2018).
"""

import itertools
from typing import Dict, List, Tuple

from besser.BUML.metamodel.object import ObjectModel
from pysat.solvers import Glucose4

from metamodels.problem_dsl import Board, Cell_Board
from metamodels.problem_validator import (
    _cell_box,
    _cell_coords,
    _get_slot_value,
    validate_problem_model,
)
from metamodels.solution_dsl import Clause, Variable
from metamodels.solution_validator import (
    CLAUSE_TO_LITERAL,
    LITERAL_TO_VARIABLE,
    _linked,
    validate_solution_model,
)

BOARD_TO_CELL = next(end for end in Cell_Board.ends if end.name == "cell")


def solve_sudoku_brute_force(problem_model: ObjectModel) -> List[Dict[Tuple[int, int], int]]:
    """Return every valid completion `{(r, c): value}` of the empty cells, in lexicographic order."""
    violations = validate_problem_model(problem_model)
    if violations:
        raise ValueError(f"Invalid Problem DSL model: {'; '.join(violations)}")

    board = next(obj for obj in problem_model.objects if obj.classifier is Board)
    size = _get_slot_value(board, "size")
    box_size = _get_slot_value(board, "boxSize")
    cells = _linked(board, BOARD_TO_CELL)

    givens = {_cell_coords(c): _get_slot_value(c, "value") for c in cells if _get_slot_value(c, "value") is not None}
    empty = sorted(_cell_coords(c) for c in cells if _get_slot_value(c, "value") is None)
    box_of = {_cell_coords(c): _cell_box(c, box_size) for c in cells}
    peer_pairs = [
        (a, b)
        for a, b in itertools.combinations(sorted(box_of), 2)
        if a[0] == b[0] or a[1] == b[1] or box_of[a] == box_of[b]
    ]

    solutions = []
    for values in itertools.product(range(1, size + 1), repeat=len(empty)):
        grid = {**givens, **dict(zip(empty, values))}
        if all(grid[a] != grid[b] for a, b in peer_pairs):
            solutions.append(dict(zip(empty, values)))
    return solutions


def solve_sat_brute_force(solution_model: ObjectModel) -> List[Dict[int, bool]]:
    """Return every satisfying assignment `{var_id: bool}` of the CNF formula."""
    violations = validate_solution_model(solution_model)
    if violations:
        raise ValueError(f"Invalid Solution DSL model: {'; '.join(violations)}")

    var_ids = sorted(
        _get_slot_value(obj, "id") for obj in solution_model.objects if obj.classifier is Variable
    )
    clauses = [
        [
            (_get_slot_value(_linked(lit, LITERAL_TO_VARIABLE)[0], "id"), _get_slot_value(lit, "isNegated"))
            for lit in _linked(clause, CLAUSE_TO_LITERAL)
        ]
        for clause in solution_model.objects
        if clause.classifier is Clause
    ]

    # SAT solvers number variables 1..n: map the model's ids (111, 122, ...) to that range,
    # otherwise every unused number below the largest id would be a free variable.
    index = {var_id: i for i, var_id in enumerate(var_ids, start=1)}
    cnf = [[-index[v] if negated else index[v] for v, negated in clause] for clause in clauses]

    with Glucose4(bootstrap_with=cnf) as solver:
        # Models omit variables that occur in no clause; those are free, so expand both values.
        models = [{var_ids[abs(lit) - 1]: lit > 0 for lit in model} for model in solver.enum_models()]
    assignments = []
    for model in models:
        free = [v for v in var_ids if v not in model]
        for values in itertools.product([False, True], repeat=len(free)):
            assignments.append({**model, **dict(zip(free, values))})
    return sorted(assignments, key=lambda a: [a[v] for v in var_ids])
