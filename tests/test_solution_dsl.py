from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.structural import (
    BinaryAssociation,
    BooleanType,
    Class,
    IntegerType,
    Multiplicity,
    Property,
    StringType,
)

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
    solution_domain_model,
    validate_solution_model,
)


def test_solution_domain_model_structure():
    assert solution_domain_model is domain_model
    assert solution_domain_model.name == "Sudoku_Solution"
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


def test_validate_clause_not_empty_violation():
    formula_obj = Formula("f").attributes(name="empty_clause_test").build()
    empty_clause = Clause("c_empty").build()
    formula_obj.clause = {empty_clause}

    om = ObjectModel(name="EmptyClauseModel", objects={formula_obj, empty_clause})
    violations = validate_solution_model(om)
    assert any("ClauseNotEmpty" in v for v in violations)


def test_validate_unique_literal_violation():
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
        name="UniqueLiteralViolationModel",
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


def test_validate_editor_imported_classes_and_end_suffixes():
    """Ensure validator works with separate Class instances and _end association end names."""
    ExtFormula = Class(name="Formula", attributes={Property(name="name", type=StringType)})
    ExtClause = Class(name="Clause", attributes=set())
    ExtLiteral = Class(name="Literal", attributes={Property(name="isNegated", type=BooleanType)})
    ExtVariable = Class(name="Variable", attributes={Property(name="id", type=IntegerType)})

    BinaryAssociation(
        name="Clause_Formula_Ext",
        ends={
            Property(name="clause_end", type=ExtClause, multiplicity=Multiplicity(0, 9999)),
            Property(
                name="formula_end",
                type=ExtFormula,
                multiplicity=Multiplicity(1, 1),
                is_composite=True,
            ),
        },
    )
    BinaryAssociation(
        name="Literal_Clause_Ext",
        ends={
            Property(name="literal_end", type=ExtLiteral, multiplicity=Multiplicity(0, 9999)),
            Property(
                name="clause_end",
                type=ExtClause,
                multiplicity=Multiplicity(1, 1),
                is_composite=True,
            ),
        },
    )
    BinaryAssociation(
        name="Literal_Variable_Ext",
        ends={
            Property(
                name="literal_end",
                type=ExtLiteral,
                multiplicity=Multiplicity(0, 9999),
                is_navigable=False,
            ),
            Property(name="variable_end", type=ExtVariable, multiplicity=Multiplicity(1, 1)),
        },
    )

    f_obj = ExtFormula("f_ext").attributes(name="ext").build()
    c_obj = ExtClause("c_ext").build()
    v_obj = ExtVariable("v_ext").attributes(id=111).build()
    l_obj = ExtLiteral("l_ext").attributes(isNegated=False).build()
    l_obj.variable_end = v_obj
    c_obj.literal_end = {l_obj}
    f_obj.clause_end = {c_obj}

    valid_om = ObjectModel(name="ValidExtModel", objects={f_obj, c_obj, v_obj, l_obj})
    assert validate_solution_model(valid_om) == []

    l_neg = ExtLiteral("l_neg_ext").attributes(isNegated=True).build()
    l_neg.variable_end = v_obj
    c_obj.literal_end = {l_obj, l_neg}
    taut_om = ObjectModel(name="TautExtModel", objects={f_obj, c_obj, v_obj, l_obj, l_neg})
    violations = validate_solution_model(taut_om)
    assert any("NoTautology" in v for v in violations)


def test_validate_empty_model_and_unlinked_literal():
    empty_om = ObjectModel(name="EmptyModel", objects=set())
    empty_violations = validate_solution_model(empty_om)
    assert len(empty_violations) > 0

    formula_obj = Formula("f").attributes(name="unlinked_test").build()
    clause_obj = Clause("c").build()
    unlinked_lit = Literal("lit_unlinked").attributes(isNegated=False).build()
    clause_obj.literal = {unlinked_lit}
    formula_obj.clause = {clause_obj}

    unlinked_om = ObjectModel(
        name="UnlinkedLiteralModel",
        objects={formula_obj, clause_obj, unlinked_lit},
    )
    unlinked_violations = validate_solution_model(unlinked_om)
    assert len(unlinked_violations) > 0


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
    assert any("Clause 'c_detached'" in v and "Formula" in v for v in containment_violations)
    assert any("Literal 'lit_orphan'" in v and "Clause" in v for v in containment_violations)

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


