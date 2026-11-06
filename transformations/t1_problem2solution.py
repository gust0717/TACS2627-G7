"""
M2M Transformation T1: Sudoku Problem DSL -> SAT/CNF Solution DSL (`transformations/t1_problem2solution.py`).

Encoding: the Part I one-hot encoding (one Boolean variable per (row, column, value),
id = 100*(row+1) + 10*(column+1) + value), with two optimisations so the formula fits the
T2 qubit budget:
  1. Given (clue) cells are known facts, so they get no variables.
  2. Values already used by a given peer (same row, column or 2x2 box) are pruned, so an
     empty cell only gets variables for its remaining candidate values.

Follows the "one function per rule" pattern over B-UML ObjectModels
(Lecture T6, Slides 6, 12, 13, 14). Every rule cites its reference:

- Rule R1 (`rule_r1_board_to_formula`):
    Board -> Formula (Brambilla et al., 2017, Ch. 8-9; Lecture T6, Slide 12)
- Rule R2 (`rule_r2_candidate_values`):
    Empty Cell -> candidate values not used by a given peer
    (Lynce & Ouaknine, 2006; Lecture T6, Slide 12)
- Rule R3 (`rule_r3_candidates_to_variables`):
    (Empty Cell, candidate value) -> Variable + record forward trace `T1Trace`
    (Lynce & Ouaknine, 2006; Lecture T6, Slide 12)
- Rule R4 (`rule_r4_exactly_one_value_clauses`):
    Each empty cell takes at least one and at most one candidate value
    (Lynce & Ouaknine, 2006; Prestwich, 2009)
- Rule R5 (`rule_r5_peer_uniqueness_clauses`):
    Two empty peer cells cannot take the same value (only common candidates)
    (Lynce & Ouaknine, 2006; Lecture T6, Slide 12)
- Rule R6 (`rule_r6_simplify_and_materialize_clauses`):
    Merge duplicate literals, drop tautologies, deduplicate clauses, and instantiate
    B-UML `Clause` and `Literal` objects (Lecture T6, Slide 14)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from besser.BUML.metamodel.object import ObjectModel

from metamodels.problem_validator import (
    _cell_box,
    _cell_coords,
    _get_slot_value,
    validate_problem_model,
)
from metamodels.solution_dsl import (
    Clause,
    Formula,
    Literal,
    Variable,
)
from metamodels.solution_validator import validate_solution_model

Coords = Tuple[int, int]
RawClause = List[Tuple[int, bool]]  # [(variable id, isNegated), ...]


class UnsatisfiableProblemError(ValueError):
    """Raised by T1 when an empty cell has no candidate value left (the puzzle has no solution)."""


def variable_id(row: int, column: int, value: int) -> int:
    """Part I variable id convention: `100*(row+1) + 10*(column+1) + value` (e.g. 111 = cell (0,0) holds 1)."""
    return 100 * (row + 1) + 10 * (column + 1) + value


def _are_peers(a, b) -> bool:
    """True if two distinct cells share a row, a column or a 2x2 box."""
    (r1, c1), (r2, c2) = _cell_coords(a), _cell_coords(b)
    return (r1, c1) != (r2, c2) and (r1 == r2 or c1 == c2 or _cell_box(a) == _cell_box(b))


@dataclass
class T1Trace:
    """
    Forward trace mapping Problem DSL empty cells to Solution DSL variable ids
    (Lecture T6, Slides 6, 13, 17): `cell_to_vars[(r, c)] = {value: variable id}`.
    """

    cell_to_vars: Dict[Coords, Dict[int, int]] = field(default_factory=dict)

    def decode_assignment(self, assignment: Dict[int, bool]) -> Dict[Coords, int]:
        """
        Decode a Boolean assignment `{variable id: bool}` into Sudoku cell values `{(row, col): value}`.

        Each empty cell must have exactly one true variable; otherwise the assignment does not
        satisfy the formula and a `ValueError` is raised.
        """
        decoded: Dict[Coords, int] = {}
        for coords, value_to_id in sorted(self.cell_to_vars.items()):
            missing = [var_id for var_id in value_to_id.values() if var_id not in assignment]
            if missing:
                raise KeyError(f"Assignment missing variable ids {missing} for cell {coords}.")
            chosen = [value for value, var_id in sorted(value_to_id.items()) if assignment[var_id]]
            if len(chosen) != 1:
                raise ValueError(
                    f"Cell {coords} must have exactly one true variable, got values {chosen}."
                )
            decoded[coords] = chosen[0]
        return decoded


def rule_r1_board_to_formula(board_obj, target_model: ObjectModel):
    """
    Rule R1: Transform a Problem DSL `Board` into a Solution DSL `Formula`.

    Literature reference:
      - Brambilla, M., Cabot, J., & Wimmer, M. (2017). *Model-Driven Software
        Engineering in Practice* (2nd ed.), Chapters 8-9 (top-level container M2M mapping).
      - Lecture T6, Slide 12 (Rule R1: `Board -> Formula`).
    """
    board_name = _get_slot_value(board_obj, "name") or getattr(board_obj, "name_", "sudoku")
    formula_name = f"{board_name}_cnf"
    formula_obj = Formula(formula_name).attributes(name=formula_name).build()
    target_model.objects.add(formula_obj)
    return formula_obj


def rule_r2_candidate_values(empty_cells, given_cells, board_size: int) -> Dict[Coords, set[int]]:
    """
    Rule R2: For each empty cell, compute the candidate values `1..size` not already used by a
    given cell in the same row, column or 2x2 box.

    Pruning these values here (instead of emitting exclusion clauses) means they never become
    variables. If an empty cell is left with no candidate, the puzzle has no solution and
    `UnsatisfiableProblemError` is raised (an empty clause would violate `ClauseNotEmpty`).

    Literature reference:
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, Proc. 9th Int.
        Symposium on Artificial Intelligence and Mathematics (ISAIM 2006) (fixed cells are
        propagated before encoding).
      - Lecture T6, Slide 12 (clue propagation).
    """
    candidates: Dict[Coords, set[int]] = {}
    for empty_obj in sorted(empty_cells, key=_cell_coords):
        used = {
            int(_get_slot_value(given_obj, "value"))
            for given_obj in given_cells
            if _are_peers(empty_obj, given_obj)
        }
        allowed = set(range(1, board_size + 1)) - used
        coords = _cell_coords(empty_obj)
        if not allowed:
            raise UnsatisfiableProblemError(
                f"Cell {coords} has no candidate value: its row, column and box already use "
                f"{sorted(used)}. The puzzle has no solution."
            )
        candidates[coords] = allowed
    return candidates


def rule_r3_candidates_to_variables(
    candidates: Dict[Coords, set[int]],
    target_model: ObjectModel,
    trace: T1Trace,
) -> Dict[int, Any]:
    """
    Rule R3: Transform each (empty cell, candidate value) pair into a `Variable` with
    id `100*(row+1) + 10*(column+1) + value`, and record the forward mapping in `T1Trace`.

    Returns `{variable id: Variable object}`.

    Literature reference:
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, ISAIM 2006
        (one Boolean variable per cell/value pair).
      - Lecture T6, Slide 12 (Rule R2: `Empty Cell -> Variables`).
    """
    var_by_id: Dict[int, Any] = {}
    for (r, c), allowed in sorted(candidates.items()):
        trace.cell_to_vars[(r, c)] = {}
        for value in sorted(allowed):
            var_id = variable_id(r, c, value)
            var_obj = Variable(f"var_{var_id}").attributes(id=var_id).build()
            target_model.objects.add(var_obj)
            var_by_id[var_id] = var_obj
            trace.cell_to_vars[(r, c)][value] = var_id
    return var_by_id


def rule_r4_exactly_one_value_clauses(candidates: Dict[Coords, set[int]]) -> List[RawClause]:
    """
    Rule R4: Each empty cell takes exactly one of its candidate values:
      - at least one: `(x_{r,c,v1} OR x_{r,c,v2} OR ...)`
      - at most one: `(NOT x_{r,c,vi} OR NOT x_{r,c,vj})` for every pair of candidates.

    A cell with a single candidate gets only the unit clause `(x_{r,c,v})`.

    Literature reference:
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, ISAIM 2006 (cell definedness
        and uniqueness clauses).
      - Prestwich, S. (2009). *CNF Encodings*, in Handbook of Satisfiability, IOS Press, Ch. 2
        (pairwise at-most-one encoding).
    """
    clauses: List[RawClause] = []
    for (r, c), allowed in sorted(candidates.items()):
        values = sorted(allowed)
        clauses.append([(variable_id(r, c, v), False) for v in values])
        for i, v1 in enumerate(values):
            for v2 in values[i + 1:]:
                clauses.append([(variable_id(r, c, v1), True), (variable_id(r, c, v2), True)])
    return clauses


def rule_r5_peer_uniqueness_clauses(
    empty_cells,
    candidates: Dict[Coords, set[int]],
) -> List[RawClause]:
    """
    Rule R5: Two empty cells that share a row, column or 2x2 box cannot take the same value:
    `(NOT x_{c1,v} OR NOT x_{c2,v})` for each value `v` that is a candidate of BOTH cells.

    Each peer pair is visited once, even if it shares both a row/column and a box.
    Peers with given values were already handled by R2 (pruning).

    Literature reference:
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, ISAIM 2006 (row, column
        and block uniqueness clauses).
      - Lecture T6, Slide 12 (Rule R5: row, column, and box peer uniqueness).
    """
    sorted_empty = sorted(empty_cells, key=_cell_coords)
    clauses: List[RawClause] = []
    for i, cell_1 in enumerate(sorted_empty):
        for cell_2 in sorted_empty[i + 1:]:
            if not _are_peers(cell_1, cell_2):
                continue
            (r1, c1), (r2, c2) = _cell_coords(cell_1), _cell_coords(cell_2)
            for value in sorted(candidates[(r1, c1)] & candidates[(r2, c2)]):
                clauses.append(
                    [(variable_id(r1, c1, value), True), (variable_id(r2, c2, value), True)]
                )
    return clauses


def rule_r6_simplify_and_materialize_clauses(
    raw_clauses: List[RawClause],
    var_by_id: Dict[int, object],
    formula_obj,
    target_model: ObjectModel,
) -> List[Any]:
    """
    Rule R6: Simplify raw clauses (merge duplicate literals, drop tautologies containing
    both `x` and `~x`, and deduplicate identical clauses) and materialize B-UML `Clause`
    and `Literal` objects in `target_model`.

    Literature reference:
      - Lecture T6, Slide 14 ("Clauses are simplified first: repeated literals merged,
        clauses with both x and ~x dropped" to satisfy `UniqueLiteral` and `NoTautology`).
      - Brambilla, M. et al. (2017). *Model-Driven Software Engineering in Practice*, Ch. 8.
    """
    simplified_clauses: List[RawClause] = []
    seen_clauses: set[Tuple[Tuple[int, bool], ...]] = set()

    for raw_clause in raw_clauses:
        if not raw_clause:
            continue

        # Merge duplicate literals and sort deterministically by (var_id, is_negated)
        unique_lits = sorted(
            {(int(var_id), bool(is_neg)) for var_id, is_neg in raw_clause},
            key=lambda item: (item[0], item[1]),
        )

        # Check for tautology: variable appearing with both False and True polarities
        polarities_by_var: Dict[int, set[bool]] = {}
        for var_id, is_neg in unique_lits:
            polarities_by_var.setdefault(var_id, set()).add(is_neg)
        if any(len(pols) > 1 for pols in polarities_by_var.values()):
            continue

        clause_key = tuple(unique_lits)
        if clause_key in seen_clauses:
            continue
        seen_clauses.add(clause_key)
        simplified_clauses.append(unique_lits)

    existing_clauses = {
        le.object
        for le in formula_obj.link_ends()
        if (
            le.name in {"clause", "clause_end"}
            or getattr(le.association_end, "name", None) in {"clause", "clause_end"}
            or getattr(getattr(le.object, "classifier", None), "name", None) == "Clause"
        )
    }
    base_idx = len(existing_clauses)

    materialized_clauses: List[Any] = []
    for offset, lits in enumerate(simplified_clauses):
        c_idx = base_idx + offset
        clause_obj = Clause(f"clause_{c_idx}").build()
        lit_objs = []
        for l_idx, (var_id, is_neg) in enumerate(lits):
            if var_id not in var_by_id:
                raise KeyError(f"Variable id={var_id} not found in var_by_id.")
            lit_obj = Literal(f"lit_{c_idx}_{l_idx}").attributes(isNegated=bool(is_neg)).build()
            lit_obj.variable = var_by_id[var_id]
            lit_objs.append(lit_obj)
            target_model.objects.add(lit_obj)

        clause_obj.literal = set(lit_objs)
        clause_obj.formula = formula_obj
        target_model.objects.add(clause_obj)
        materialized_clauses.append(clause_obj)

    return materialized_clauses


def transform_t1(problem_model: ObjectModel) -> Tuple[ObjectModel, T1Trace]:
    """
    Execute Transformation T1 (Problem DSL -> Solution DSL).

    Validates the input Problem DSL model, executes Rules R1-R6 deterministically,
    and validates the resulting Solution DSL model against all OCL invariants.

    Returns:
        `(solution_object_model, t1_trace)`

    Raises:
        ValueError: the Problem DSL model is invalid, has no empty cell, or is not 4x4.
        UnsatisfiableProblemError: an empty cell has no candidate value (no solution exists).
    """
    problem_violations = validate_problem_model(problem_model)
    if problem_violations:
        raise ValueError(
            f"Invalid Problem DSL model: {'; '.join(problem_violations)}"
        )

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
    board_name = _get_slot_value(board_obj, "name") or getattr(board_obj, "name_", "sudoku")
    board_size = int(_get_slot_value(board_obj, "size"))
    if board_size != 4:
        raise ValueError(
            f"Transformation T1 only supports 4x4 boards (size=4, got {board_size})."
        )

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

    # A cell is a clue when it has a value (Part I also allows isGiven=False with a value).
    empty_cells = [c for c in cells if _get_slot_value(c, "value") is None]
    given_cells = [c for c in cells if _get_slot_value(c, "value") is not None]

    if not empty_cells:
        raise ValueError(
            f"Board '{board_name}' has 0 empty cells; at least one cell must be empty."
        )

    target_model = ObjectModel(
        name=f"{board_name}_Solution_ObjectModel",
        objects=set(),
    )
    trace = T1Trace()

    # Rule R1: Board -> Formula
    formula_obj = rule_r1_board_to_formula(board_obj, target_model)

    # Rule R2: Empty Cells -> candidate values (prune values used by given peers)
    candidates = rule_r2_candidate_values(empty_cells, given_cells, board_size)

    # Rule R3: (Empty Cell, candidate value) -> Variable + Trace
    var_by_id = rule_r3_candidates_to_variables(candidates, target_model, trace)

    # Rule R4: Exactly one value per empty cell
    r4_clauses = rule_r4_exactly_one_value_clauses(candidates)

    # Rule R5: Empty peer cells take different values
    r5_clauses = rule_r5_peer_uniqueness_clauses(empty_cells, candidates)

    # Rule R6: Simplify and Materialize Clauses
    rule_r6_simplify_and_materialize_clauses(
        r4_clauses + r5_clauses, var_by_id, formula_obj, target_model
    )

    solution_violations = validate_solution_model(target_model)
    if solution_violations:
        raise ValueError(
            f"Invalid Solution DSL model produced by T1: {'; '.join(solution_violations)}"
        )

    return target_model, trace
