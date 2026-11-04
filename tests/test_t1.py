"""
Unit Tests for Transformation T1 (`tests/test_t1.py`).

See Lecture T6, Slide 18 ("Testing T1: Classical Enumeration"):
- Verify Problem DSL OCL invariants on input models.
- Verify Solution DSL OCL invariants on T1 output models.
- Enumerate all satisfying SAT assignments in `{0,1}^n` and assert they match
  the classical Sudoku completions 1-to-1 via `T1Trace`.
"""

import pytest
from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.structural import (
    BooleanType,
    IntegerType,
    StringType,
)

from config.solver_config import SolverConfig
from metamodels.problem_dsl import (
    Board,
    Board_boxSize,
    Board_name,
    Board_size,
    BoxCoherent,
    BoxSizePositive,
    Cell,
    Cell_Board,
    Cell_box,
    Cell_column,
    Cell_isGiven,
    Cell_row,
    Cell_value,
    CellCount,
    ConsistentValues,
    GivenFlagValid,
    PositionValid,
    SizeConsistent,
    UniquePositions,
    ValueValid,
    build_sudoku_board_model,
    domain_model,
    problem_domain_model,
    validate_problem_model,
)
from metamodels.solution_dsl import (
    Formula,
    Variable,
    validate_solution_model,
)
from transformations.t1_problem2solution import (
    T1Trace,
    rule_r2_empty_cells_to_variables,
    rule_r4_given_clue_exclusion_clauses,
    rule_r5_peer_uniqueness_clauses,
    rule_r6_simplify_and_materialize_clauses,
    transform_t1,
)


def test_problem_dsl_metamodel_structure():
    assert problem_domain_model is domain_model
    assert problem_domain_model.name == "Sudoku"
    assert {c.name for c in problem_domain_model.types if hasattr(c, "attributes")} >= {
        "Board",
        "Cell",
    }
    assert {p.name for p in Board.attributes} == {"name", "size", "boxSize"}
    assert Board_name.type is StringType
    assert Board_size.type is IntegerType
    assert Board_boxSize.type is IntegerType

    assert {p.name for p in Cell.attributes} == {
        "row",
        "column",
        "box",
        "isGiven",
        "value",
    }
    assert Cell_row.type is IntegerType
    assert Cell_column.type is IntegerType
    assert Cell_box.type is IntegerType
    assert Cell_isGiven.type is BooleanType
    assert Cell_value.type is IntegerType
    assert Cell_value.is_optional is True

    assert problem_domain_model.associations == {Cell_Board}
    cb_ends = {e.name: e for e in Cell_Board.ends}
    assert (cb_ends["cell"].multiplicity.min, cb_ends["cell"].multiplicity.max) == (0, 9999)
    assert (cb_ends["board"].multiplicity.min, cb_ends["board"].multiplicity.max) == (1, 1)
    assert cb_ends["board"].is_composite is True

    expected_constraints = {
        BoxSizePositive,
        SizeConsistent,
        GivenFlagValid,
        CellCount,
        UniquePositions,
        ConsistentValues,
        PositionValid,
        ValueValid,
        BoxCoherent,
    }
    assert problem_domain_model.constraints == expected_constraints
    assert {c.name for c in problem_domain_model.constraints} == {
        "BoxSizePositive",
        "SizeConsistent",
        "GivenFlagValid",
        "CellCount",
        "UniquePositions",
        "ConsistentValues",
        "PositionValid",
        "ValueValid",
        "BoxCoherent",
    }


def test_build_and_validate_valid_problem_model():
    model = build_sudoku_board_model(
        "part1_board",
        [
            [1, 0, None, 0],
            [0, 0, 2, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 4],
        ],
    )
    assert validate_problem_model(model) == []


def test_validate_problem_model_ocl_violations():
    # 1. Empty model (no Board)
    empty_om = ObjectModel(name="EmptyProblem", objects=set())
    assert any("Board" in v for v in validate_problem_model(empty_om))

    # 2. BoxSizePositive & SizeConsistent
    b_bad_box = Board("b_bad").attributes(name="bad_box", boxSize=0, size=4).build()
    om_bad_box = ObjectModel(name="BadBoxModel", objects={b_bad_box})
    violations = validate_problem_model(om_bad_box)
    assert any("BoxSizePositive" in v for v in violations)
    assert any("SizeConsistent" in v for v in violations)
    assert any("CellCount" in v for v in violations)

    # 3. CellCount & unlinked cell (1..1 Board link)
    b_partial = Board("b_part").attributes(name="part", boxSize=2, size=4).build()
    c_linked = Cell("c_0_0").attributes(row=0, column=0, box=0, isGiven=False).build()
    c_orphan = Cell("c_orphan").attributes(row=0, column=1, box=0, isGiven=False).build()
    b_partial.cell = {c_linked}
    om_partial = ObjectModel(name="PartialModel", objects={b_partial, c_linked, c_orphan})
    violations = validate_problem_model(om_partial)
    assert any("CellCount" in v for v in violations)
    assert any("c_orphan" in v and "Board" in v for v in violations)

    # 4. UniquePositions
    dup_model = build_sudoku_board_model(
        "dup_pos",
        [
            [1, 0, 0, 0],
            [0, 0, 2, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 4],
        ],
    )
    cell_0_1 = next(o for o in dup_model.objects if o.name_ == "cell_0_1")
    for slot in cell_0_1.slots:
        if slot.attribute.name == "column":
            slot.value.value = 0
    violations = validate_problem_model(dup_model)
    assert any("UniquePositions" in v for v in violations)

    # 5. ConsistentValues (row, column, box)
    row_dup_model = build_sudoku_board_model(
        "row_dup",
        [
            [1, 0, 1, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ],
    )
    assert any("ConsistentValues" in v for v in validate_problem_model(row_dup_model))

    col_dup_model = build_sudoku_board_model(
        "col_dup",
        [
            [2, 0, 0, 0],
            [0, 0, 0, 0],
            [2, 0, 0, 0],
            [0, 0, 0, 0],
        ],
    )
    assert any("ConsistentValues" in v for v in validate_problem_model(col_dup_model))

    box_dup_model = build_sudoku_board_model(
        "box_dup",
        [
            [3, 0, 0, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ],
    )
    assert any("ConsistentValues" in v for v in validate_problem_model(box_dup_model))

    # 6. PositionValid & BoxCoherent
    pos_box_model = build_sudoku_board_model(
        "pos_box",
        [
            [1, 0, 0, 0],
            [0, 0, 2, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 4],
        ],
    )
    cell_0_0 = next(o for o in pos_box_model.objects if o.name_ == "cell_0_0")
    cell_0_2 = next(o for o in pos_box_model.objects if o.name_ == "cell_0_2")
    for slot in cell_0_0.slots:
        if slot.attribute.name == "row":
            slot.value.value = 4
    for slot in cell_0_2.slots:
        if slot.attribute.name == "box":
            slot.value.value = 3
    violations = validate_problem_model(pos_box_model)
    assert any("PositionValid" in v for v in violations)
    assert any("BoxCoherent" in v for v in violations)

    # 7. GivenFlagValid (isGiven=True with value=None) & ValueValid (value > size)
    given_val_model = build_sudoku_board_model(
        "given_val",
        [
            [1, 0, 0, 0],
            [0, 0, 2, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 4],
        ],
    )
    c_empty_given_true = next(o for o in given_val_model.objects if o.name_ == "cell_0_1")
    for slot in c_empty_given_true.slots:
        if slot.attribute.name == "isGiven":
            slot.value.value = True
    c_bad_value = next(o for o in given_val_model.objects if o.name_ == "cell_1_2")
    for slot in c_bad_value.slots:
        if slot.attribute.name == "value":
            slot.value.value = 5
    violations = validate_problem_model(given_val_model)
    assert any("GivenFlagValid" in v for v in violations)
    assert any("ValueValid" in v for v in violations)

    # 8. Bool disguised as int on Board and Cell integer attributes
    bool_int_model = build_sudoku_board_model(
        "bool_int",
        [
            [1, 0, 0, 0],
            [0, 0, 2, 0],
            [0, 3, 0, 0],
            [0, 0, 0, 4],
        ],
    )
    board_obj = next(o for o in bool_int_model.objects if o.classifier.name == "Board")
    for slot in board_obj.slots:
        if slot.attribute.name in {"size", "boxSize"}:
            slot.value.value = True
    c00 = next(o for o in bool_int_model.objects if o.name_ == "cell_0_0")
    for slot in c00.slots:
        if slot.attribute.name in {"row", "column", "box", "value"}:
            slot.value.value = True
    violations = validate_problem_model(bool_int_model)
    assert any("BoxSizePositive" in v or "boxSize" in v for v in violations)
    assert any("SizeConsistent" in v or "size" in v for v in violations)
    assert any("PositionValid" in v or "row" in v for v in violations)
    assert any("BoxCoherent" in v or "box" in v for v in violations)
    assert any("ValueValid" in v or "value" in v for v in violations)


def test_solver_config_grover_rounds():
    assert SolverConfig(num_solutions=1).compute_grover_rounds(4) == 3
    assert SolverConfig(num_solutions=2).compute_grover_rounds(4) == 2
    assert SolverConfig(num_solutions=0).compute_grover_rounds(4) == 0
    assert SolverConfig(num_solutions=1).compute_grover_rounds(0) == 0
    assert SolverConfig(num_solutions=1, grover_rounds=5).compute_grover_rounds(4) == 5

    with pytest.raises(ValueError, match="encoding"):
        SolverConfig(encoding="invalid")

    with pytest.raises(ValueError, match="shots"):
        SolverConfig(shots=0)


def _extract_clauses_as_sorted_tuples(sol_model: ObjectModel) -> list[list[tuple[int, bool]]]:
    """Helper to extract clauses from a Solution DSL ObjectModel as sorted (var_id, is_negated) lists."""
    clauses = sorted(
        [
            obj
            for obj in sol_model.objects
            if getattr(getattr(obj, "classifier", None), "name", None) == "Clause"
        ],
        key=lambda o: getattr(o, "name_", ""),
    )
    result: list[list[tuple[int, bool]]] = []
    for clause_obj in clauses:
        lits = [
            le.object
            for le in clause_obj.link_ends()
            if (
                le.name in {"literal", "literal_end"}
                or getattr(le.association_end, "name", None) in {"literal", "literal_end"}
                or getattr(getattr(le.object, "classifier", None), "name", None) == "Literal"
            )
        ]
        clause_tuples: list[tuple[int, bool]] = []
        for lit_obj in lits:
            is_neg = next(
                slot.value.value
                for slot in lit_obj.slots
                if slot.attribute.name == "isNegated"
            )
            var_obj = next(
                le.object
                for le in lit_obj.link_ends()
                if (
                    le.name in {"variable", "variable_end"}
                    or getattr(le.association_end, "name", None) in {"variable", "variable_end"}
                    or getattr(getattr(le.object, "classifier", None), "name", None) == "Variable"
                )
            )
            var_id = next(
                slot.value.value
                for slot in var_obj.slots
                if slot.attribute.name == "id"
            )
            clause_tuples.append((var_id, is_neg))
        clause_tuples.sort(key=lambda pair: (pair[0], pair[1]))
        result.append(clause_tuples)
    return result


def test_t1_trace_decode_assignment():
    trace = T1Trace(cell_to_vars={(0, 1): [121, 120]})
    assert trace.encoding == "binary"
    assert trace.decode_assignment({121: False, 120: False}) == {(0, 1): 1}
    assert trace.decode_assignment({121: False, 120: True}) == {(0, 1): 2}
    assert trace.decode_assignment({121: True, 120: False}) == {(0, 1): 3}
    assert trace.decode_assignment({121: True, 120: True}) == {(0, 1): 4}


def test_t1_single_empty_cell_clauses_and_trace():
    # 1 empty cell at (0, 1); given peers in row 0, col 1, box 0 contain {1, 3, 4}, leaving {2}
    problem_model = build_sudoku_board_model(
        "tiny_board",
        [
            [1, 0, 3, 4],
            [3, 4, 1, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    sol_model, trace = transform_t1(problem_model, SolverConfig())

    assert trace.cell_to_vars == {(0, 1): [121, 120]}
    assert validate_solution_model(sol_model) == []

    clauses = _extract_clauses_as_sorted_tuples(sol_model)
    assert len(clauses) == 3
    assert clauses == [
        [(120, False), (121, False)],  # forbids 1 (b1=0, b0=0)
        [(120, False), (121, True)],   # forbids 3 (b1=1, b0=0)
        [(120, True), (121, True)],    # forbids 4 (b1=1, b0=1)
    ]


def test_t1_peer_uniqueness_filters_common_candidates_and_deduplicates_peers():
    # Construct two empty cells (0, 0) and (0, 1) in the same row AND 2x2 box
    # sharing given peers with values {3, 4}
    c_0_0 = Cell("cell_0_0").attributes(row=0, column=0, box=0, isGiven=False).build()
    c_0_1 = Cell("cell_0_1").attributes(row=0, column=1, box=0, isGiven=False).build()
    g_0_2 = Cell("cell_0_2").attributes(row=0, column=2, box=1, isGiven=True, value=3).build()
    g_0_3 = Cell("cell_0_3").attributes(row=0, column=3, box=1, isGiven=True, value=4).build()
    g_1_0 = Cell("cell_1_0").attributes(row=1, column=0, box=0, isGiven=True, value=3).build()
    g_1_1 = Cell("cell_1_1").attributes(row=1, column=1, box=0, isGiven=True, value=4).build()

    empty_cells = [c_0_1, c_0_0]  # intentionally unsorted to verify deterministic sorting
    given_cells = [g_0_2, g_0_3, g_1_0, g_1_1]

    target_model = ObjectModel(name="TargetCNF", objects=set())
    trace = T1Trace()
    config = SolverConfig()

    cell_vars = rule_r2_empty_cells_to_variables(empty_cells, target_model, config, trace)
    assert list(trace.cell_to_vars.keys()) == [(0, 0), (0, 1)]

    r4_clauses, allowed_values = rule_r4_given_clue_exclusion_clauses(
        empty_cells, given_cells, cell_vars, config
    )
    assert allowed_values == {(0, 0): {1, 2}, (0, 1): {1, 2}}
    assert len(r4_clauses) == 4  # 2 forbidden values ({3, 4}) for each of the 2 empty cells

    r5_clauses = rule_r5_peer_uniqueness_clauses(
        empty_cells, allowed_values, cell_vars, config
    )
    # Only 2 four-literal clauses (for common allowed values 1 and 2), NOT 4 or 8
    assert len(r5_clauses) == 2
    assert all(len(clause) == 4 for clause in r5_clauses)
    assert [sorted(c) for c in r5_clauses] == [
        [(110, False), (111, False), (120, False), (121, False)],  # forbids both = 1
        [(110, True), (111, False), (120, True), (121, False)],    # forbids both = 2
    ]


def test_rule_r6_merges_duplicates_and_drops_tautologies():
    formula_obj = Formula("test_f").attributes(name="test_cnf").build()
    var_111 = Variable("var_0_0_b1").attributes(id=111).build()
    var_110 = Variable("var_0_0_b0").attributes(id=110).build()
    target_model = ObjectModel(name="R6Model", objects={formula_obj, var_111, var_110})
    var_by_id = {111: var_111, 110: var_110}

    raw_clauses_first = [
        [(111, False), (111, False)],          # duplicate literals -> [(111, False)]
        [(111, False), (111, True)],           # tautology -> dropped
        [(111, False)],                        # identical to first simplified clause -> deduplicated
    ]

    clauses_1 = rule_r6_simplify_and_materialize_clauses(
        raw_clauses_first, var_by_id, formula_obj, target_model
    )
    assert len(clauses_1) == 1

    # Incremental second call when formula_obj already has exactly 1 linked Clause
    raw_clauses_second = [
        [(111, True), (110, False), (111, True)],  # duplicate + unsorted -> [(110, False), (111, True)]
    ]
    clauses_2 = rule_r6_simplify_and_materialize_clauses(
        raw_clauses_second, var_by_id, formula_obj, target_model
    )
    assert len(clauses_2) == 1
    assert validate_solution_model(target_model) == []
    assert _extract_clauses_as_sorted_tuples(target_model) == [
        [(111, False)],
        [(110, False), (111, True)],
    ]


def test_t1_rejects_invalid_or_fully_solved_board():
    # 1. Invalid problem model (empty ObjectModel)
    invalid_model = ObjectModel(name="Invalid", objects=set())
    with pytest.raises(ValueError, match="Invalid Problem DSL model"):
        transform_t1(invalid_model)

    # 2. Fully solved board (0 empty cells)
    solved_model = build_sudoku_board_model(
        "solved",
        [
            [1, 2, 3, 4],
            [3, 4, 1, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    with pytest.raises(ValueError, match="empty"):
        transform_t1(solved_model)

    # 3. Valid 9x9 board (box_size=3, with at least one empty cell) rejected by 4x4 binary encoding guard
    board_9x9 = build_sudoku_board_model(
        "board_9x9",
        [[0] * 9 for _ in range(9)],
        box_size=3,
    )
    with pytest.raises(ValueError, match="size=4"):
        transform_t1(board_9x9)

    # 4. Deterministic execution across two runs
    puzzle_model = build_sudoku_board_model(
        "det_board",
        [
            [1, 0, 3, 4],
            [3, 4, 0, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    sol_1, trace_1 = transform_t1(puzzle_model)
    sol_2, trace_2 = transform_t1(puzzle_model)

    assert trace_1.cell_to_vars == trace_2.cell_to_vars
    assert _extract_clauses_as_sorted_tuples(sol_1) == _extract_clauses_as_sorted_tuples(sol_2)


def _count_vars_and_clauses(sol_model: ObjectModel) -> tuple[int, int]:
    """Return `(num_variables, num_clauses)` in a Solution DSL ObjectModel."""
    objects = getattr(sol_model, "objects", set()) or set()
    num_vars = sum(
        1 for o in objects if getattr(getattr(o, "classifier", None), "name", None) == "Variable"
    )
    num_clauses = sum(
        1 for o in objects if getattr(getattr(o, "classifier", None), "name", None) == "Clause"
    )
    return num_vars, num_clauses


def test_t1_classical_enumeration_tiny_unique_solution():
    from tests.classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force

    # E = 1 empty cell at (0, 1); unique valid value is 2 (M = 1)
    problem_model = build_sudoku_board_model(
        "tiny",
        [
            [1, 0, 3, 4],
            [3, 4, 1, 2],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    assert validate_problem_model(problem_model) == []

    config = SolverConfig(num_solutions=1)
    sol_model, trace = transform_t1(problem_model, config)
    assert validate_solution_model(sol_model) == []

    n, m = _count_vars_and_clauses(sol_model)
    assert (n, m) == (2, 3)
    assert n + m <= 20
    assert config.compute_grover_rounds(n) == 1

    sudoku_solutions = solve_sudoku_brute_force(problem_model)
    sat_assignments = solve_sat_brute_force(sol_model)
    decoded_sat_solutions = [trace.decode_assignment(a) for a in sat_assignments]

    assert len(sudoku_solutions) == 1
    assert len(sat_assignments) == 1
    assert decoded_sat_solutions == sudoku_solutions == [{(0, 1): 2}]


def test_t1_classical_enumeration_medium_unique_solution():
    from tests.classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force

    # E = 3 empty cells at (0, 0), (0, 1), (2, 0); unique solution M = 1 requiring both R4 and R5
    problem_model = build_sudoku_board_model(
        "medium",
        [
            [0, 0, 3, 4],
            [3, 4, 1, 2],
            [0, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    assert validate_problem_model(problem_model) == []

    config = SolverConfig(num_solutions=1)
    sol_model, trace = transform_t1(problem_model, config)
    assert validate_solution_model(sol_model) == []

    n, m = _count_vars_and_clauses(sol_model)
    assert (n, m) == (6, 10)
    assert n + m <= 20
    assert config.compute_grover_rounds(n) == 6

    sudoku_solutions = solve_sudoku_brute_force(problem_model)
    sat_assignments = solve_sat_brute_force(sol_model)
    decoded_sat_solutions = [trace.decode_assignment(a) for a in sat_assignments]

    assert len(sudoku_solutions) == 1
    assert len(sat_assignments) == 1
    assert decoded_sat_solutions == sudoku_solutions == [
        {(0, 0): 1, (0, 1): 2, (2, 0): 2}
    ]


def test_t1_classical_enumeration_many_solutions():
    from tests.classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force

    # E = 4 empty cells at (0, 0), (0, 1), (2, 0), (2, 1) forming a 2x2 intercalate with M = 2 solutions
    problem_model = build_sudoku_board_model(
        "many",
        [
            [0, 0, 3, 4],
            [3, 4, 1, 2],
            [0, 0, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    assert validate_problem_model(problem_model) == []

    config = SolverConfig(num_solutions=2)
    sol_model, trace = transform_t1(problem_model, config)
    assert validate_solution_model(sol_model) == []

    n, m = _count_vars_and_clauses(sol_model)
    assert (n, m) == (8, 16)
    assert n <= 12  # within <= 12 search qubits requirement
    assert config.compute_grover_rounds(n) == 8

    sudoku_solutions = solve_sudoku_brute_force(problem_model)
    sat_assignments = solve_sat_brute_force(sol_model)
    decoded_sat_solutions = [trace.decode_assignment(a) for a in sat_assignments]

    expected_solutions = [
        {(0, 0): 1, (0, 1): 2, (2, 0): 2, (2, 1): 1},
        {(0, 0): 2, (0, 1): 1, (2, 0): 1, (2, 1): 2},
    ]
    assert len(sudoku_solutions) == 2
    assert len(sat_assignments) == 2
    assert sudoku_solutions == expected_solutions
    assert decoded_sat_solutions == sudoku_solutions


def test_t1_classical_enumeration_unsatisfiable_none():
    from tests.classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force

    # E = 2 empty cells at (0, 1) and (1, 3); all given clues satisfy ConsistentValues,
    # but empty cell (0, 1)'s peers collectively contain {1, 2, 3, 4}, yielding M = 0
    problem_model = build_sudoku_board_model(
        "none",
        [
            [1, 0, 3, 4],
            [3, 2, 1, 0],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
    )
    assert validate_problem_model(problem_model) == []

    config = SolverConfig(num_solutions=0)
    sol_model, trace = transform_t1(problem_model, config)
    assert validate_solution_model(sol_model) == []

    n, m = _count_vars_and_clauses(sol_model)
    assert (n, m) == (4, 8)
    assert n + m <= 20
    assert config.compute_grover_rounds(n) == 0

    sudoku_solutions = solve_sudoku_brute_force(problem_model)
    sat_assignments = solve_sat_brute_force(sol_model)
    decoded_sat_solutions = [trace.decode_assignment(a) for a in sat_assignments]

    assert sudoku_solutions == []
    assert sat_assignments == []
    assert decoded_sat_solutions == []


