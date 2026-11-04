"""
M2M Transformation T1: Sudoku Problem DSL -> SAT/CNF Solution DSL (`transformations/t1_problem2solution.py`).

Follows the "one function per rule" pattern over B-UML ObjectModels
(Lecture T6, Slides 6, 12, 13, 14). Every rule cites its peer-reviewed reference:

- Rule R1 (`rule_r1_board_to_formula`):
    Board -> Formula (Brambilla et al., 2017, Ch. 8-9; Lecture T6, Slide 12)
- Rule R2 (`rule_r2_empty_cells_to_variables`):
    Empty Cell(r, c) -> Variable(s) + record forward trace `T1Trace`
    (Yato & Seta, 2003; Prestwich, 2009; Lecture T6, Slide 12)
- Rule R3 (`rule_r3_cell_domain_clauses`):
    Cell domain validity clauses (Prestwich, 2009; Lecture T6, Slide 12)
- Rule R4 (`rule_r4_given_clue_exclusion_clauses`):
    Given clue exclusion clauses pruning values present in row/col/box peers
    (Lynce & Ouaknine, 2006; Yato & Seta, 2003)
- Rule R5 (`rule_r5_peer_uniqueness_clauses`):
    Pairwise row, column, and 2x2 box uniqueness clauses between empty cells
    (Yato & Seta, 2003; Lynce & Ouaknine, 2006; Lecture T6, Slide 12)
- Rule R6 (`rule_r6_simplify_and_materialize_clauses`):
    Merge duplicate literals, drop tautologies, deduplicate clauses, and instantiate
    B-UML `Clause` and `Literal` objects (Lecture T6, Slide 14)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from besser.BUML.metamodel.object import ObjectModel

from config.solver_config import SolverConfig
from metamodels.problem_dsl import validate_problem_model
from metamodels.solution_dsl import (
    Clause,
    Formula,
    Literal,
    Variable,
    validate_solution_model,
)


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
    """Return the 2x2 box index of a Problem DSL `Cell` object."""
    box_val = _get_slot_value(cell_obj, "box")
    if isinstance(box_val, int) and not isinstance(box_val, bool):
        return box_val
    r, c = _cell_coords(cell_obj)
    return (r // box_size) * box_size + (c // box_size)


def _extract_var_ids(var_Pair: List) -> Tuple[int, int]:
    """Extract `(id_b1, id_b0)` from a list of two Variable objects or integer IDs."""
    v1, v0 = var_Pair[0], var_Pair[1]
    id_b1 = v1 if isinstance(v1, int) else int(_get_slot_value(v1, "id"))
    id_b0 = v0 if isinstance(v0, int) else int(_get_slot_value(v0, "id"))
    return id_b1, id_b0


def _forbid_value_literals(var_pair: List, value: int) -> List[Tuple[int, bool]]:
    """
    Build the 2-literal De Morgan disjunction forbidding `cell == value`.

    With 2-bit binary encoding:
      d = value - 1 in {0, 1, 2, 3}
      bit_1 = (d >> 1) & 1, bit_0 = d & 1
      ~(b_1 == bit_1 /\\ b_0 == bit_0) <=> (b_1 != bit_1) \\/ (b_0 != bit_0)
    Thus literal polarity `isNegated` is `bool(bit_k)`.
    """
    id_b1, id_b0 = _extract_var_ids(var_pair)
    d = value - 1
    bit_1 = (d >> 1) & 1
    bit_0 = d & 1
    return [(id_b1, bool(bit_1)), (id_b0, bool(bit_0))]


@dataclass
class T1Trace:
    """
    Forward trace mapping Problem DSL empty cells to Solution DSL variable IDs
    (Lecture T6, Slides 6, 13, 17).
    """

    cell_to_vars: Dict[Tuple[int, int], List[int]] = field(default_factory=dict)
    encoding: str = "binary"

    def decode_assignment(self, assignment: Dict[int, bool]) -> Dict[Tuple[int, int], int]:
        """
        Decode a Boolean variable assignment `{var_id: bool}` into Sudoku cell values
        `{(row, col): value}` using `v = 1 + 2 * int(b_1) + int(b_0)`.
        """
        if self.encoding != "binary":
            raise ValueError(f"Unsupported encoding {self.encoding!r}.")

        decoded: Dict[Tuple[int, int], int] = {}
        for (r, c), var_ids in sorted(self.cell_to_vars.items()):
            if len(var_ids) != 2:
                raise ValueError(
                    f"Expected 2 binary variable IDs for cell {(r, c)}, got {var_ids!r}."
                )
            id_b1, id_b0 = var_ids[0], var_ids[1]
            if id_b1 not in assignment or id_b0 not in assignment:
                raise KeyError(
                    f"Assignment missing variable IDs for cell {(r, c)}: expected {id_b1} and {id_b0}."
                )
            b1 = int(bool(assignment[id_b1]))
            b0 = int(bool(assignment[id_b0]))
            decoded[(r, c)] = 1 + 2 * b1 + b0
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


def rule_r2_empty_cells_to_variables(
    empty_cells,
    target_model: ObjectModel,
    config: SolverConfig,
    trace: T1Trace,
) -> Dict[Tuple[int, int], List]:
    """
    Rule R2: Transform each empty `Cell(r, c)` into 2 binary `Variable` objects `[b_1, b_0]`
    and record the forward mapping in `T1Trace`.

    Variable ID convention:
      - MSB (`b_1`): `100 * (r + 1) + 10 * (c + 1) + 1` (`var_{r}_{c}_b1`)
      - LSB (`b_0`): `100 * (r + 1) + 10 * (c + 1) + 0` (`var_{r}_{c}_b0`)

    Literature reference:
      - Yato, T., & Seta, T. (2003). *Complexity and Completeness of Finding Another
        Solution and Its Application to Puzzles*, IEICE Trans. Fundamentals, E86-A(5), 1052-1060.
      - Prestwich, S. (2009). *CNF Encodings*, in Handbook of Satisfiability, IOS Press, Ch. 2
        (compact binary representation of finite-domain variables).
      - Lecture T6, Slide 12 (Rule R2: `Empty Cell -> Variables`).
    """
    if config.encoding != "binary":
        raise ValueError(f"Unsupported encoding {config.encoding!r}.")

    trace.encoding = config.encoding
    sorted_empty = sorted(empty_cells, key=_cell_coords)
    cell_vars: Dict[Tuple[int, int], List] = {}

    for cell_obj in sorted_empty:
        r, c = _cell_coords(cell_obj)
        id_b1 = 100 * (r + 1) + 10 * (c + 1) + 1
        id_b0 = 100 * (r + 1) + 10 * (c + 1) + 0

        var_b1 = Variable(f"var_{r}_{c}_b1").attributes(id=id_b1).build()
        var_b0 = Variable(f"var_{r}_{c}_b0").attributes(id=id_b0).build()

        target_model.objects.add(var_b1)
        target_model.objects.add(var_b0)

        cell_vars[(r, c)] = [var_b1, var_b0]
        trace.cell_to_vars[(r, c)] = [id_b1, id_b0]

    return cell_vars


def rule_r3_cell_domain_clauses(
    empty_cells,
    cell_vars,
    board_size: int,
    config: SolverConfig,
) -> List[List[Tuple[int, bool]]]:
    """
    Rule R3: Generate cell domain validity clauses forbidding out-of-range binary states.

    For 4x4 Sudoku (`board_size == 4`) with 2-bit binary encoding, 2^2 = 4 matches
    the domain `{1, 2, 3, 4}` bijectively, so no invalid bit combinations exist and
    zero domain clauses are emitted.

    Literature reference:
      - Prestwich, S. (2009). *CNF Encodings*, in Handbook of Satisfiability, IOS Press, Ch. 2
        (binary encoding domain bounds when domain size equals a power of two).
      - Lecture T6, Slide 12 (Rules R3-R4: cell domain constraints).
    """
    if config.encoding != "binary":
        raise ValueError(f"Unsupported encoding {config.encoding!r}.")

    clauses: List[List[Tuple[int, bool]]] = []
    if board_size < 4:
        for cell_obj in sorted(empty_cells, key=_cell_coords):
            coords = _cell_coords(cell_obj)
            for invalid_val in range(board_size + 1, 5):
                clauses.append(_forbid_value_literals(cell_vars[coords], invalid_val))
    return clauses


def rule_r4_given_clue_exclusion_clauses(
    empty_cells,
    given_cells,
    cell_vars,
    config: SolverConfig,
) -> Tuple[List[List[Tuple[int, bool]]], Dict[Tuple[int, int], set[int]]]:
    """
    Rule R4: For each empty cell, forbid any value `v` already assigned to a given clue
    cell in the same row, column, or 2x2 box via a 2-literal De Morgan clause, and compute
    the remaining candidate set `allowed_values[(r, c)]`.

    Literature reference:
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, Proc. 9th Int.
        Symposium on Artificial Intelligence and Mathematics (ISAIM 2006).
      - Yato, T., & Seta, T. (2003). *Complexity and Completeness of Finding Another
        Solution and Its Application to Puzzles*, IEICE Trans. Fundamentals, E86-A(5).
      - Lecture T6, Slide 12 (clue propagation / unary exclusions).
    """
    if config.encoding != "binary":
        raise ValueError(f"Unsupported encoding {config.encoding!r}.")

    sorted_empty = sorted(empty_cells, key=_cell_coords)
    sorted_given = sorted(given_cells, key=_cell_coords)

    clauses: List[List[Tuple[int, bool]]] = []
    allowed_values: Dict[Tuple[int, int], set[int]] = {}

    for empty_obj in sorted_empty:
        r, c = _cell_coords(empty_obj)
        b = _cell_box(empty_obj)

        forbidden: set[int] = set()
        for given_obj in sorted_given:
            gr, gc = _cell_coords(given_obj)
            gb = _cell_box(given_obj)
            gval = _get_slot_value(given_obj, "value")
            if gval is not None and (r == gr or c == gc or b == gb):
                forbidden.add(int(gval))

        for val in sorted(forbidden):
            clauses.append(_forbid_value_literals(cell_vars[(r, c)], val))

        allowed_values[(r, c)] = {1, 2, 3, 4} - forbidden

    return clauses, allowed_values


def rule_r5_peer_uniqueness_clauses(
    empty_cells,
    allowed_values: Dict[Tuple[int, int], set[int]],
    cell_vars,
    config: SolverConfig,
) -> List[List[Tuple[int, bool]]]:
    """
    Rule R5: Generate pairwise uniqueness clauses between distinct peer empty cells
    `(c_1, c_2)` that share a row, column, or 2x2 box.

    Each ordered peer pair `(c_1, c_2)` with `c_1 < c_2` is visited once (even if they
    share both a row/column and a 2x2 box) and emits a 4-literal clause forbidding
    `c_1 == v /\\ c_2 == v` only for common candidate values
    `v in sorted(allowed_values[c_1] & allowed_values[c_2])`.

    Literature reference:
      - Yato, T., & Seta, T. (2003). *Complexity and Completeness of Finding Another
        Solution and Its Application to Puzzles*, IEICE Trans. Fundamentals, E86-A(5).
      - Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*, ISAIM 2006.
      - Lecture T6, Slide 12 (Rule R5: row, column, and box peer uniqueness).
    """
    if config.encoding != "binary":
        raise ValueError(f"Unsupported encoding {config.encoding!r}.")

    sorted_empty = sorted(empty_cells, key=_cell_coords)
    clauses: List[List[Tuple[int, bool]]] = []

    for i in range(len(sorted_empty)):
        c1_obj = sorted_empty[i]
        r1, col1 = _cell_coords(c1_obj)
        b1 = _cell_box(c1_obj)
        c1_allowed = allowed_values.get((r1, col1), {1, 2, 3, 4})

        for j in range(i + 1, len(sorted_empty)):
            c2_obj = sorted_empty[j]
            r2, col2 = _cell_coords(c2_obj)
            b2 = _cell_box(c2_obj)

            if not (r1 == r2 or col1 == col2 or b1 == b2):
                continue

            c2_allowed = allowed_values.get((r2, col2), {1, 2, 3, 4})
            common_candidates = sorted(c1_allowed & c2_allowed)

            for val in common_candidates:
                clause = _forbid_value_literals(cell_vars[(r1, col1)], val) + _forbid_value_literals(
                    cell_vars[(r2, col2)], val
                )
                clauses.append(clause)

    return clauses


def rule_r6_simplify_and_materialize_clauses(
    raw_clauses: List[List[Tuple[int, bool]]],
    var_by_id: Dict[int, object],
    formula_obj,
    target_model: ObjectModel,
) -> List:
    """
    Rule R6: Simplify raw clauses (merge duplicate literals, drop tautologies containing
    both `x` and `~x`, and deduplicate identical clauses) and materialize B-UML `Clause`
    and `Literal` objects in `target_model`.

    Literature reference:
      - Lecture T6, Slide 14 ("Clauses are simplified first: repeated literals merged,
        clauses with both x and ~x dropped" to satisfy `UniqueLiteral` and `NoTautology`).
      - Brambilla, M. et al. (2017). *Model-Driven Software Engineering in Practice*, Ch. 8.
    """
    simplified_clauses: List[List[Tuple[int, bool]]] = []
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

    materialized_clauses: List = []
    for c_idx, lits in enumerate(simplified_clauses):
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
        target_model.objects.add(clause_obj)
        materialized_clauses.append(clause_obj)

    existing_clauses = getattr(formula_obj, "clause", None) or set()
    formula_obj.clause = set(existing_clauses) | set(materialized_clauses)
    return materialized_clauses


def transform_t1(
    problem_model: ObjectModel,
    config: Optional[SolverConfig] = None,
) -> Tuple[ObjectModel, T1Trace]:
    """
    Execute Transformation T1 (Problem DSL -> Solution DSL).

    Validates the input Problem DSL model, executes Rules R1-R6 deterministically,
    and validates the resulting Solution DSL model against all OCL invariants.

    Returns:
        `(solution_object_model, t1_trace)`
    """
    if config is None:
        config = SolverConfig()

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
    trace = T1Trace(encoding=config.encoding)

    # Rule R1: Board -> Formula
    formula_obj = rule_r1_board_to_formula(board_obj, target_model)

    # Rule R2: Empty Cells -> Variables + Trace
    cell_vars = rule_r2_empty_cells_to_variables(empty_cells, target_model, config, trace)

    # Rule R3: Cell Domain Clauses
    r3_clauses = rule_r3_cell_domain_clauses(empty_cells, cell_vars, board_size, config)

    # Rule R4: Given Clue Exclusion Clauses
    r4_clauses, allowed_values = rule_r4_given_clue_exclusion_clauses(
        empty_cells, given_cells, cell_vars, config
    )

    # Rule R5: Pairwise Peer Uniqueness Clauses
    r5_clauses = rule_r5_peer_uniqueness_clauses(
        empty_cells, allowed_values, cell_vars, config
    )

    # Rule R6: Simplify and Materialize Clauses
    var_by_id = {
        int(_get_slot_value(var_obj, "id")): var_obj
        for vars_pair in cell_vars.values()
        for var_obj in vars_pair
    }
    raw_clauses = r3_clauses + r4_clauses + r5_clauses
    rule_r6_simplify_and_materialize_clauses(
        raw_clauses, var_by_id, formula_obj, target_model
    )

    solution_violations = validate_solution_model(target_model)
    if solution_violations:
        raise ValueError(
            f"Invalid Solution DSL model produced by T1: {'; '.join(solution_violations)}"
        )

    return target_model, trace
