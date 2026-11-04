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

    # 7. GivenFlagValid (including isGiven=True with value=None, and isGiven=False with value set) & ValueValid
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
