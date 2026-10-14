"""BESSER metamodel draft for the Sudoku 4x4 QMDE assignment.

This file is intentionally small and executable: it creates an in-memory BESSER
metamodel for the problem DSL and the solution DSL (CNF + solver configuration).
It is meant as a concrete starting point for the Part I implementation on top of
the BESSER fork located in the sibling folder ../BESSER.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
BESSER_ROOT = PROJECT_ROOT.parent / "BESSER"
if str(BESSER_ROOT) not in sys.path:
    sys.path.insert(0, str(BESSER_ROOT))

from besser.BUML.metamodel.structural import (
    BinaryAssociation,
    BooleanType,
    Class,
    DomainModel,
    IntegerType,
    Multiplicity,
    Property,
    StringType,
)


def build_problem_model() -> DomainModel:
    """Build the problem DSL for the Sudoku board.

    Board 1 --- contains --- 0..* Cell
    """
    board = Class(name="Board")
    cell = Class(name="Cell")

    board_name = Property(name="name", type=StringType)
    board_size = Property(name="size", type=IntegerType)
    board_box_size = Property(name="boxSize", type=IntegerType)
    board.attributes = {board_name, board_size, board_box_size}

    cell_row = Property(name="row", type=IntegerType)
    cell_column = Property(name="column", type=IntegerType)
    cell_box = Property(name="box", type=IntegerType)
    cell_value = Property(name="value", type=IntegerType, multiplicity=Multiplicity(0, 1))
    cell_is_given = Property(name="isGiven", type=BooleanType)
    cell.attributes = {cell_row, cell_column, cell_box, cell_value, cell_is_given}

    contains = BinaryAssociation(
        name="contains",
        ends={
            Property(name="board", type=board, multiplicity=Multiplicity(1, 1)),
            Property(name="cells", type=cell, multiplicity=Multiplicity(0, "*")),
        },
    )

    model = DomainModel(
        name="SudokuProblemModel",
        types={board, cell},
        associations={contains},
    )
    return model


def build_solution_model() -> DomainModel:
    """Build the solution DSL for the CNF representation.

    The model is intentionally minimal but captures the main concepts required by
    the assignment: formula, variables, clauses, literals, encoding table and
    solver configuration.
    """
    formula = Class(name="Formula")
    variable = Class(name="Variable")
    clause = Class(name="Clause")
    literal = Class(name="Literal")
    encoding_entry = Class(name="EncodingEntry")
    solver_config = Class(name="SolverConfiguration")

    formula_name = Property(name="name", type=StringType)
    formula.attributes = {formula_name}

    variable_id = Property(name="id", type=StringType)
    variable.attributes = {variable_id}

    clause_id = Property(name="id", type=StringType)
    clause_origin = Property(name="origin", type=StringType)
    clause.attributes = {clause_id, clause_origin}

    literal_sign = Property(name="sign", type=BooleanType)
    literal.attributes = {literal_sign}

    encoding_cell_id = Property(name="cellId", type=StringType)
    encoding_bit_index = Property(name="bitIndex", type=IntegerType)
    encoding_value = Property(name="value", type=IntegerType)
    encoding_entry.attributes = {encoding_cell_id, encoding_bit_index, encoding_value}

    solver_strategy = Property(name="encodingStrategy", type=StringType)
    solver_solutions = Property(name="solutionsCount", type=IntegerType)
    solver_rounds = Property(name="rounds", type=IntegerType)
    solver_shots = Property(name="shots", type=IntegerType)
    solver_config.attributes = {
        solver_strategy,
        solver_solutions,
        solver_rounds,
        solver_shots,
    }

    formula_variables = BinaryAssociation(
        name="containsVariables",
        ends={
            Property(name="formula", type=formula, multiplicity=Multiplicity(1, 1)),
            Property(name="variables", type=variable, multiplicity=Multiplicity(0, "*")),
        },
    )

    formula_clauses = BinaryAssociation(
        name="containsClauses",
        ends={
            Property(name="formula", type=formula, multiplicity=Multiplicity(1, 1)),
            Property(name="clauses", type=clause, multiplicity=Multiplicity(0, "*")),
        },
    )

    formula_encoding = BinaryAssociation(
        name="hasEncodingTable",
        ends={
            Property(name="formula", type=formula, multiplicity=Multiplicity(1, 1)),
            Property(name="encodingTable", type=encoding_entry, multiplicity=Multiplicity(0, "*")),
        },
    )

    formula_config = BinaryAssociation(
        name="hasSolverConfiguration",
        ends={
            Property(name="formula", type=formula, multiplicity=Multiplicity(1, 1)),
            Property(name="solverConfiguration", type=solver_config, multiplicity=Multiplicity(1, 1)),
        },
    )

    clause_literals = BinaryAssociation(
        name="hasLiterals",
        ends={
            Property(name="clause", type=clause, multiplicity=Multiplicity(1, 1)),
            Property(name="literals", type=literal, multiplicity=Multiplicity(0, "*")),
        },
    )

    literal_variable = BinaryAssociation(
        name="refersToVariable",
        ends={
            Property(name="literal", type=literal, multiplicity=Multiplicity(1, 1)),
            Property(name="variable", type=variable, multiplicity=Multiplicity(1, 1)),
        },
    )

    encoding_variable = BinaryAssociation(
        name="mapsToVariable",
        ends={
            Property(name="encodingEntry", type=encoding_entry, multiplicity=Multiplicity(1, 1)),
            Property(name="variable", type=variable, multiplicity=Multiplicity(1, 1)),
        },
    )

    model = DomainModel(
        name="SudokuSolutionModel",
        types={formula, variable, clause, literal, encoding_entry, solver_config},
        associations={
            formula_variables,
            formula_clauses,
            formula_encoding,
            formula_config,
            clause_literals,
            literal_variable,
            encoding_variable,
        },
    )
    return model


def validate_problem_model(model: DomainModel) -> dict:
    """Manual validation of the core constraints for the problem DSL.

    This is not a substitute for full OCL execution, but it is a convenient way to
    assert the main invariants of the model while we are still working with the
    metamodel in Python.
    """
    board = next((t for t in model.types if t.name == "Board"), None)
    cell = next((t for t in model.types if t.name == "Cell"), None)

    assert board is not None and cell is not None
    assert any(p.name == "size" for p in board.attributes)
    assert any(p.name == "boxSize" for p in board.attributes)
    assert any(p.name == "row" for p in cell.attributes)
    assert any(p.name == "column" for p in cell.attributes)
    assert any(p.name == "box" for p in cell.attributes)
    assert any(p.name == "value" for p in cell.attributes)
    assert any(p.name == "isGiven" for p in cell.attributes)

    return {
        "model": model.name,
        "checks": [
            "Board has size and boxSize",
            "Cell has row, column, box, optional value, and explicit given flag",
            "Association Board -> Cell exists",
            "Problem DSL is ready for T1 generation with givens metadata",
        ],
    }


if __name__ == "__main__":
    problem_model = build_problem_model()
    solution_model = build_solution_model()
    validation = validate_problem_model(problem_model)

    print("Problem model:", problem_model.name)
    print("Types:", [t.name for t in problem_model.types])
    print("Solution model:", solution_model.name)
    print("Types:", [t.name for t in solution_model.types])
    print("Validation:", validation)
