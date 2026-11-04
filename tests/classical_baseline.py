"""
Classical Brute-Force Baselines (`tests/classical_baseline.py`).

Provides the ground-truth classical solvers required by Lecture T6 (Slides 18, 19, 22):
1. `solve_sudoku_brute_force(problem_model)`:
   Enumerates all valid Sudoku completions for a Problem DSL model.
2. `solve_sat_brute_force(solution_model)`:
   Enumerates all satisfying truth assignments `{var_id: bool}` in `{0,1}^n`
   for a Solution DSL CNF model.
"""

import itertools
from typing import Dict, List, Tuple

from besser.BUML.metamodel.object import ObjectModel

from metamodels.problem_dsl import validate_problem_model
from metamodels.solution_dsl import validate_solution_model


def _get_slot_value(obj, attr_name: str):
    """Return the primitive value stored in `obj`'s slot for `attr_name`, or None if unset."""
    for slot in getattr(obj, "slots", []):
        if getattr(slot.attribute, "name", None) == attr_name:
            return slot.value.value
    return None


def _cell_coords(cell_obj) -> Tuple[int, int]:
    """Return `(row, column)` coordinates of a Problem DSL `Cell` object."""
    return (int(_get_slot_value(cell_obj, "row")), int(_get_slot_value(cell_obj, "column")))


def _cell_box(cell_obj, box_size: int = 2) -> int:
    """Return the box index of a Problem DSL `Cell` object."""
    box_val = _get_slot_value(cell_obj, "box")
    if isinstance(box_val, int) and not isinstance(box_val, bool):
        return box_val
    r, c = _cell_coords(cell_obj)
    return (r // box_size) * box_size + (c // box_size)


def solve_sudoku_brute_force(
    problem_model: ObjectModel,
) -> List[Dict[Tuple[int, int], int]]:
    """
    Enumerate all valid Sudoku completions for a Problem DSL `ObjectModel`.

    Extracts board size, box size, given cells, and empty cells (sorted by `(row, col)`),
    recursively assigns candidate values `1..size` consistent with all row, column, and
    box peers, and returns all valid completions `{(r, c): val}` in lexicographical order.
    """
    violations = validate_problem_model(problem_model)
    if violations:
        raise ValueError(f"Invalid Problem DSL model: {'; '.join(violations)}")

    objects = getattr(problem_model, "objects", set()) or set()
    boards = sorted(
        [
            obj
            for obj in objects
            if getattr(getattr(obj, "classifier", None), "name", None) == "Board"
        ],
        key=lambda o: getattr(o, "name_", ""),
    )
    board_obj = boards[0]
    size = int(_get_slot_value(board_obj, "size"))
    box_size = int(_get_slot_value(board_obj, "boxSize"))

    linked_cells = [
        le.object
        for le in board_obj.link_ends()
        if (
            le.name in {"cell", "cell_end"}
            or getattr(le.association_end, "name", None) in {"cell", "cell_end"}
            or getattr(getattr(le.object, "classifier", None), "name", None) == "Cell"
        )
    ]
    cells = sorted(linked_cells, key=_cell_coords)

    # Record fixed values and empty cell coordinates
    fixed_values: Dict[Tuple[int, int], int] = {}
    box_of: Dict[Tuple[int, int], int] = {}
    empty_coords: List[Tuple[int, int]] = []

    for cell_obj in cells:
        r, c = _cell_coords(cell_obj)
        b = _cell_box(cell_obj, box_size)
        box_of[(r, c)] = b
        val = _get_slot_value(cell_obj, "value")
        if val is None:
            empty_coords.append((r, c))
        else:
            fixed_values[(r, c)] = int(val)

    all_coords = sorted(box_of.keys())
    peers_of: Dict[Tuple[int, int], List[Tuple[int, int]]] = {}
    for r1, c1 in all_coords:
        b1 = box_of[(r1, c1)]
        peers_of[(r1, c1)] = [
            (r2, c2)
            for (r2, c2) in all_coords
            if (r1, c1) != (r2, c2) and (r1 == r2 or c1 == c2 or b1 == box_of[(r2, c2)])
        ]

    solutions: List[Dict[Tuple[int, int], int]] = []
    current_assignment: Dict[Tuple[int, int], int] = {}

    def _is_consistent(coord: Tuple[int, int], candidate: int) -> bool:
        for peer in peers_of[coord]:
            peer_val = fixed_values.get(peer, current_assignment.get(peer))
            if peer_val == candidate:
                return False
        return True

    def _backtrack(idx: int) -> None:
        if idx == len(empty_coords):
            solutions.append(dict(current_assignment))
            return

        coord = empty_coords[idx]
        for candidate in range(1, size + 1):
            if _is_consistent(coord, candidate):
                current_assignment[coord] = candidate
                _backtrack(idx + 1)
                del current_assignment[coord]

    _backtrack(0)
    return solutions


def solve_sat_brute_force(
    solution_model: ObjectModel,
) -> List[Dict[int, bool]]:
    """
    Enumerate all satisfying Boolean assignments `{var_id: bool}` for a Solution DSL `ObjectModel`.

    Extracts all `Variable` IDs (sorted ascending) and `Clause` literal lists `[(var_id, is_negated), ...]`,
    iterates over `itertools.product([False, True], repeat=len(var_ids))`, and returns every truth
    assignment that satisfies all clauses.
    """
    violations = validate_solution_model(solution_model)
    if violations:
        raise ValueError(f"Invalid Solution DSL model: {'; '.join(violations)}")

    objects = getattr(solution_model, "objects", set()) or set()
    variables = [
        obj
        for obj in objects
        if getattr(getattr(obj, "classifier", None), "name", None) == "Variable"
    ]
    var_ids = sorted({int(_get_slot_value(v, "id")) for v in variables})

    clauses_objs = sorted(
        [
            obj
            for obj in objects
            if getattr(getattr(obj, "classifier", None), "name", None) == "Clause"
        ],
        key=lambda o: getattr(o, "name_", ""),
    )

    clauses: List[List[Tuple[int, bool]]] = []
    for clause_obj in clauses_objs:
        lits = sorted(
            [
                le.object
                for le in clause_obj.link_ends()
                if (
                    le.name in {"literal", "literal_end"}
                    or getattr(le.association_end, "name", None) in {"literal", "literal_end"}
                    or getattr(getattr(le.object, "classifier", None), "name", None) == "Literal"
                )
            ],
            key=lambda o: getattr(o, "name_", ""),
        )
        clause_lits: List[Tuple[int, bool]] = []
        for lit_obj in lits:
            is_neg = bool(_get_slot_value(lit_obj, "isNegated"))
            var_obj = next(
                le.object
                for le in lit_obj.link_ends()
                if (
                    le.name in {"variable", "variable_end"}
                    or getattr(le.association_end, "name", None) in {"variable", "variable_end"}
                    or getattr(getattr(le.object, "classifier", None), "name", None) == "Variable"
                )
            )
            var_id = int(_get_slot_value(var_obj, "id"))
            clause_lits.append((var_id, is_neg))
        clauses.append(clause_lits)

    satisfying_assignments: List[Dict[int, bool]] = []
    for bits in itertools.product([False, True], repeat=len(var_ids)):
        assignment = dict(zip(var_ids, bits))
        if all(
            any(
                (not assignment[var_id]) if is_neg else assignment[var_id]
                for var_id, is_neg in clause
            )
            for clause in clauses
        ):
            satisfying_assignments.append(assignment)

    return satisfying_assignments
