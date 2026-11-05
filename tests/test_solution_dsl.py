from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.structural import BooleanType, IntegerType, StringType

from metamodels.solution_dsl import (
    Clause,
    Clause_Formula,
    ClauseNotEmpty,
    Formula,
    Formula_name,
    Literal,
    Literal_Clause,
    Literal_isNegated,
    Literal_Variable,
    NoTautology,
    UniqueLiteral,
    Variable,
    Variable_id,
    domain_model,
    object_model,
)
from metamodels.solution_validator import validate_solution_model

# The BESSER export names the DomainModel after the class diagram title.
solution_domain_model = domain_model


def test_solution_domain_model_structure():
    assert solution_domain_model.name == "Class_Diagram"
    assert {c.name for c in solution_domain_model.types if hasattr(c, "attributes")} >= {
        "Formula",
        "Clause",
        "Literal",
        "Variable",
    }
    assert {p.name for p in Formula.attributes} == {"name"}
    assert Formula_name.type is StringType
    assert {p.name for p in Clause.attributes} == set()
    assert {p.name for p in Literal.attributes} == {"isNegated"}
    assert Literal_isNegated.type is BooleanType
    assert {p.name for p in Variable.attributes} == {"id"}
    assert Variable_id.type is IntegerType
    assert solution_domain_model.associations == {
        Clause_Formula,
        Literal_Clause,
        Literal_Variable,
    }
    cf_ends = {e.name: e for e in Clause_Formula.ends}
    assert (cf_ends["clause"].multiplicity.min, cf_ends["clause"].multiplicity.max) == (0, 9999)
    assert (cf_ends["formula"].multiplicity.min, cf_ends["formula"].multiplicity.max) == (1, 1)
    assert cf_ends["formula"].is_composite is True

    lc_ends = {e.name: e for e in Literal_Clause.ends}
    assert (lc_ends["literal"].multiplicity.min, lc_ends["literal"].multiplicity.max) == (0, 9999)
    assert (lc_ends["clause"].multiplicity.min, lc_ends["clause"].multiplicity.max) == (1, 1)
    assert lc_ends["clause"].is_composite is True

    lv_ends = {e.name: e for e in Literal_Variable.ends}
    assert (lv_ends["literal"].multiplicity.min, lv_ends["literal"].multiplicity.max) == (0, 9999)
    assert lv_ends["literal"].is_navigable is False
    assert (lv_ends["variable"].multiplicity.min, lv_ends["variable"].multiplicity.max) == (1, 1)
    assert lv_ends["variable"].is_navigable is True

    assert solution_domain_model.constraints == {
        ClauseNotEmpty,
        UniqueLiteral,
        NoTautology,
    }


def test_validate_part1_cell_0_0_instance_valid():
    """Part I Section 2.4 hand-crafted CNF formula instance for cell(0,0)."""
    formula_obj = Formula("sudoku_cnf").attributes(name="sudoku_4x4").build()

    var_ids = [111, 121, 131, 141, 211, 311, 411, 221]
    variables = {
        vid: Variable(f"var_{vid}").attributes(id=vid).build()
        for vid in var_ids
    }

    # Unit clause for the given clue: (x_111)
    c_given = Clause("c_given").build()
    lit_g = Literal("lit_g").attributes(isNegated=False).build()
    lit_g.variable = variables[111]
    c_given.literal = {lit_g}

    # Binary exclusion clauses for row 0, col 0, and box 0: (~x_111 v ~x_peer)
    clause_specs = [
        ("c_row_01", "r1", 121),
        ("c_row_02", "r2", 131),
        ("c_row_03", "r3", 141),
        ("c_col_10", "c1", 211),
        ("c_col_20", "c2", 311),
        ("c_col_30", "c3", 411),
        ("c_box_11", "b", 221),
    ]

    clauses = {c_given}
    literals = {lit_g}

    for clause_name, prefix, peer_id in clause_specs:
        clause_obj = Clause(clause_name).build()
        lit_a = Literal(f"lit_{prefix}_a").attributes(isNegated=True).build()
        lit_b = Literal(f"lit_{prefix}_b").attributes(isNegated=True).build()
        lit_a.variable = variables[111]
        lit_b.variable = variables[peer_id]
        clause_obj.literal = {lit_a, lit_b}
        clauses.add(clause_obj)
        literals.update({lit_a, lit_b})

    formula_obj.clause = clauses

    om = ObjectModel(
        name="Sudoku_Solution_Instance",
        objects={formula_obj, *clauses, *literals, *variables.values()},
    )
    assert validate_solution_model(om) == []


def test_validate_besser_exported_part1_instance_valid():
    """The object diagram exported from BESSER (Part I Section 2.4) satisfies all invariants."""
    assert validate_solution_model(object_model) == []
    names = {o.classifier.name for o in object_model.objects}
    assert names == {"Formula", "Clause", "Literal", "Variable"}
    assert sum(1 for o in object_model.objects if o.classifier.name == "Clause") == 8


def test_validate_clause_not_empty_violation():
    formula_obj = Formula("f").attributes(name="empty_clause_test").build()
    empty_clause = Clause("c_empty").build()
    formula_obj.clause = {empty_clause}

    om = ObjectModel(name="EmptyClauseModel", objects={formula_obj, empty_clause})
    violations = validate_solution_model(om)
    assert any("ClauseNotEmpty" in v for v in violations)


def test_validate_unique_literal_violation():
    """Same polarity on one shared Variable object: the case the OCL describes."""
    formula_obj = Formula("f").attributes(name="dup_literal_test").build()
    clause_obj = Clause("c_dup").build()
    var_111 = Variable("var_111").attributes(id=111).build()
    lit_1 = Literal("lit_1").attributes(isNegated=False).build()
    lit_2 = Literal("lit_2").attributes(isNegated=False).build()
    lit_1.variable = var_111
    lit_2.variable = var_111
    clause_obj.literal = {lit_1, lit_2}
    formula_obj.clause = {clause_obj}

    om = ObjectModel(
        name="UniqueLiteralViolationModel",
        objects={formula_obj, clause_obj, lit_1, lit_2, var_111},
    )
    violations = validate_solution_model(om)
    assert violations == [
        "UniqueLiteral violated on Clause 'c_dup': duplicate literal for variable id=111 with isNegated=False."
    ]


def test_validate_unique_literal_by_variable_id():
    """Two Variable objects with the same id count as the same variable (stricter than the OCL)."""
    formula_obj = Formula("f").attributes(name="dup_literal_test").build()
    clause_obj = Clause("c_dup").build()
    var_a = Variable("var_111_a").attributes(id=111).build()
    var_b = Variable("var_111_b").attributes(id=111).build()
    lit_1 = Literal("lit_1").attributes(isNegated=False).build()
    lit_2 = Literal("lit_2").attributes(isNegated=False).build()
    lit_1.variable = var_a
    lit_2.variable = var_b
    clause_obj.literal = {lit_1, lit_2}
    formula_obj.clause = {clause_obj}

    om = ObjectModel(
        name="UniqueLiteralByIdModel",
        objects={formula_obj, clause_obj, lit_1, lit_2, var_a, var_b},
    )
    violations = validate_solution_model(om)
    assert any("UniqueLiteral" in v for v in violations)
    assert not any("NoTautology" in v for v in violations)
    assert not any("ClauseNotEmpty" in v for v in violations)


def test_validate_no_tautology_violation():
    formula_obj = Formula("f").attributes(name="tautology_test").build()
    clause_obj = Clause("c_taut").build()
    var_111 = Variable("var_111").attributes(id=111).build()
    lit_pos = Literal("lit_pos").attributes(isNegated=False).build()
    lit_neg = Literal("lit_neg").attributes(isNegated=True).build()
    lit_pos.variable = var_111
    lit_neg.variable = var_111
    clause_obj.literal = {lit_pos, lit_neg}
    formula_obj.clause = {clause_obj}

    om = ObjectModel(
        name="NoTautologyViolationModel",
        objects={formula_obj, clause_obj, lit_pos, lit_neg, var_111},
    )
    violations = validate_solution_model(om)
    assert any("NoTautology" in v for v in violations)
    assert not any("UniqueLiteral" in v for v in violations)
    assert not any("ClauseNotEmpty" in v for v in violations)


def test_validate_empty_model_and_unlinked_literal():
    empty_om = ObjectModel(name="EmptyModel", objects=set())
    assert validate_solution_model(empty_om) == [
        "Model contains no Formula object.",
        "Model contains no Clause objects.",
    ]

    formula_obj = Formula("f").attributes(name="unlinked_test").build()
    clause_obj = Clause("c").build()
    unlinked_lit = Literal("lit_unlinked").attributes(isNegated=False).build()
    clause_obj.literal = {unlinked_lit}
    formula_obj.clause = {clause_obj}

    unlinked_om = ObjectModel(
        name="UnlinkedLiteralModel",
        objects={formula_obj, clause_obj, unlinked_lit},
    )
    assert validate_solution_model(unlinked_om) == [
        "Object 'lit_unlinked' violates multiplicity 1..1 for association end 'variable' "
        "of association 'Literal_Variable' (found 0 links)."
    ]


def test_validate_containment_and_attribute_type_violations():
    """Verify containment checks (Clause->Formula, Literal->Clause) and strict attribute types."""
    # 1. Clause not linked to Formula and orphaned Literal not linked to Clause
    formula_obj = Formula("f").attributes(name="").build()
    detached_clause = Clause("c_detached").build()
    var_111 = Variable("v_111").attributes(id=111).build()
    lit_in_clause = Literal("lit_ok").attributes(isNegated=False).build()
    lit_in_clause.variable = var_111
    detached_clause.literal = {lit_in_clause}

    orphan_lit = Literal("lit_orphan").attributes(isNegated=False).build()
    orphan_lit.variable = var_111

    om_containment = ObjectModel(
        name="ContainmentViolationModel",
        objects={formula_obj, detached_clause, var_111, lit_in_clause, orphan_lit},
    )
    containment_violations = validate_solution_model(om_containment)
    assert any("Formula 'f'" in v and "name" in v for v in containment_violations)
    assert any(
        "'c_detached' violates multiplicity 1..1 for association end 'formula'" in v
        for v in containment_violations
    )
    assert any(
        "'lit_orphan' violates multiplicity 1..1 for association end 'clause'" in v
        for v in containment_violations
    )

    # 2. Invalid types on Variable.id (bool is a subclass of int in Python, so BESSER allows id=True)
    #    and missing Literal.isNegated slot
    f_types = Formula("f_types").attributes(name="type_test").build()
    c_types = Clause("c_types").build()
    var_bool_id = Variable("v_bool").attributes(id=True).build()
    lit_missing_neg = Literal("l_missing_neg").build()
    lit_missing_neg.variable = var_bool_id
    c_types.literal = {lit_missing_neg}
    f_types.clause = {c_types}

    om_types = ObjectModel(
        name="TypeViolationModel",
        objects={f_types, c_types, var_bool_id, lit_missing_neg},
    )
    type_violations = validate_solution_model(om_types)
    assert any("Variable 'v_bool'" in v and "integer" in v for v in type_violations)

    # Fix Variable.id to integer so Literal.isNegated missing/boolean check is reached
    var_int_id = Variable("v_int").attributes(id=111).build()
    lit_missing_neg.variable = var_int_id
    om_lit_type = ObjectModel(
        name="LiteralTypeViolationModel",
        objects={f_types, c_types, var_int_id, lit_missing_neg},
    )
    lit_type_violations = validate_solution_model(om_lit_type)
    assert any("Literal 'l_missing_neg'" in v and "boolean" in v for v in lit_type_violations)


