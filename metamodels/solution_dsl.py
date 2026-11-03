"""
Solution DSL — SAT / CNF Formula Metamodel & OCL Constraints (`metamodels/solution_dsl.py`).

Refactored from Part I (`part1/Sudoku Solution DSL.json`) following Lecture T6, Slide 22.
"""

from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.structural import (
    BinaryAssociation,
    BooleanType,
    Class,
    Constraint,
    DomainModel,
    IntegerType,
    Multiplicity,
    Property,
    StringType,
)

# Classes
Formula = Class(name="Formula")
Clause = Class(name="Clause")
Literal = Class(name="Literal")
Variable = Class(name="Variable")

# Formula class attributes
Formula_name: Property = Property(name="name", type=StringType)
Formula.attributes = {Formula_name}

# Clause class attributes
Clause.attributes = set()

# Literal class attributes
Literal_isNegated: Property = Property(name="isNegated", type=BooleanType)
Literal.attributes = {Literal_isNegated}

# Variable class attributes
Variable_id: Property = Property(name="id", type=IntegerType)
Variable.attributes = {Variable_id}

# Relationships
Clause_Formula: BinaryAssociation = BinaryAssociation(
    name="Clause_Formula",
    ends={
        Property(name="clause", type=Clause, multiplicity=Multiplicity(0, 9999)),
        Property(name="formula", type=Formula, multiplicity=Multiplicity(1, 1), is_composite=True),
    },
)

Literal_Clause: BinaryAssociation = BinaryAssociation(
    name="Literal_Clause",
    ends={
        Property(name="literal", type=Literal, multiplicity=Multiplicity(0, 9999)),
        Property(name="clause", type=Clause, multiplicity=Multiplicity(1, 1), is_composite=True),
    },
)

Literal_Variable: BinaryAssociation = BinaryAssociation(
    name="Literal_Variable",
    ends={
        Property(name="literal", type=Literal, multiplicity=Multiplicity(0, 9999), is_navigable=False),
        Property(name="variable", type=Variable, multiplicity=Multiplicity(1, 1)),
    },
)

# OCL Constraints
ClauseNotEmpty: Constraint = Constraint(
    name="ClauseNotEmpty",
    context=Clause,
    expression="context Clause inv ClauseNotEmpty: self.literal->size() > 0",
    language="OCL",
    description="Clause Not Empty",
)

UniqueLiteral: Constraint = Constraint(
    name="UniqueLiteral",
    context=Clause,
    expression=(
        "context Clause inv UniqueLiteral: "
        "self.literal->forAll(l1, l2 | l1 <> l2 implies (l1.variable <> l2.variable or l1.isNegated <> l2.isNegated))"
    ),
    language="OCL",
    description="No two literals in the same clause may represent the exact same variable with the same polarity.",
)

NoTautology: Constraint = Constraint(
    name="NoTautology",
    context=Clause,
    expression=(
        "context Clause inv NoTautology: "
        "self.literal->forAll(l1, l2 | (l1 <> l2 and l1.variable = l2.variable) implies l1.isNegated = l2.isNegated)"
    ),
    language="OCL",
    description="No clause may simultaneously contain a literal and its negation (x_i and not x_i).",
)

# Domain Model
solution_domain_model = DomainModel(
    name="Sudoku_Solution",
    types={Formula, Clause, Literal, Variable},
    associations={Clause_Formula, Literal_Clause, Literal_Variable},
    constraints={ClauseNotEmpty, UniqueLiteral, NoTautology},
    generalizations=set(),
    metadata=None,
)

domain_model = solution_domain_model


def _get_slot_value(obj, attr_name: str):
    """Return the primitive value stored in `obj`'s slot for `attr_name`, or None if unset."""
    for slot in getattr(obj, "slots", []):
        if getattr(slot.attribute, "name", None) == attr_name:
            return slot.value.value
    return None


def validate_solution_model(model: ObjectModel) -> list[str]:
    """
    Validate the Solution DSL OCL invariants in Python (see Lecture T6, Slide 20).

    Checks:
      - Model contains at least one Formula and at least one Clause.
      - Every Literal has `isNegated` set and references a Variable with `id` set.
      - ClauseNotEmpty: every Clause has at least one Literal.
      - UniqueLiteral: no Clause has duplicate literals (same variable id and polarity).
      - NoTautology: no Clause contains both a literal and its negation (same variable id, opposite polarity).

    Returns:
        A list of violation messages (empty list if valid).
    """
    violations: list[str] = []

    objects = getattr(model, "objects", set()) or set()
    formulas = [
        obj for obj in objects if getattr(getattr(obj, "classifier", None), "name", None) == "Formula"
    ]
    clauses = [
        obj for obj in objects if getattr(getattr(obj, "classifier", None), "name", None) == "Clause"
    ]
    literals = [
        obj for obj in objects if getattr(getattr(obj, "classifier", None), "name", None) == "Literal"
    ]

    if not formulas:
        violations.append("Model contains no Formula object.")
    if not clauses:
        violations.append("Model contains no Clause objects.")

    for formula_obj in sorted(formulas, key=lambda o: getattr(o, "name_", "")):
        formula_obj_name = getattr(formula_obj, "name_", "<unnamed>")
        formula_name_val = _get_slot_value(formula_obj, "name")
        if not isinstance(formula_name_val, str) or not formula_name_val.strip():
            violations.append(
                f"Formula '{formula_obj_name}' must have a non-empty string attribute 'name'."
            )

    for lit_obj in sorted(literals, key=lambda o: getattr(o, "name_", "")):
        lit_name = getattr(lit_obj, "name_", "<unnamed>")
        linked_clauses = [
            le.object
            for le in lit_obj.link_ends()
            if (
                le.name in {"clause", "clause_end"}
                or getattr(le.association_end, "name", None) in {"clause", "clause_end"}
                or getattr(getattr(le.object, "classifier", None), "name", None) == "Clause"
            )
        ]
        if len(linked_clauses) != 1:
            violations.append(
                f"Literal '{lit_name}' must belong to exactly one Clause (found {len(linked_clauses)})."
            )

    for clause_obj in sorted(clauses, key=lambda o: getattr(o, "name_", "")):
        clause_name = getattr(clause_obj, "name_", "<unnamed>")
        linked_formulas = [
            le.object
            for le in clause_obj.link_ends()
            if (
                le.name in {"formula", "formula_end"}
                or getattr(le.association_end, "name", None) in {"formula", "formula_end"}
                or getattr(getattr(le.object, "classifier", None), "name", None) == "Formula"
            )
        ]
        if len(linked_formulas) != 1:
            violations.append(
                f"Clause '{clause_name}' must belong to exactly one Formula (found {len(linked_formulas)})."
            )

        clause_literals = [
            le.object
            for le in clause_obj.link_ends()
            if (
                le.name in {"literal", "literal_end"}
                or getattr(le.association_end, "name", None) in {"literal", "literal_end"}
                or getattr(getattr(le.object, "classifier", None), "name", None) == "Literal"
            )
        ]

        if len(clause_literals) == 0:
            violations.append(
                f"ClauseNotEmpty violated on Clause '{clause_name}': clause must contain at least one literal."
            )
            continue

        seen_polarities_by_var: dict[int, set[bool]] = {}
        seen_pairs: set[tuple[int, bool]] = set()
        reported_unique_vars: set[tuple[int, bool]] = set()
        reported_tautology_vars: set[int] = set()

        for lit_obj in sorted(clause_literals, key=lambda o: getattr(o, "name_", "")):
            lit_name = getattr(lit_obj, "name_", "<unnamed>")
            linked_vars = [
                le.object
                for le in lit_obj.link_ends()
                if (
                    le.name in {"variable", "variable_end"}
                    or getattr(le.association_end, "name", None) in {"variable", "variable_end"}
                    or getattr(getattr(le.object, "classifier", None), "name", None) == "Variable"
                )
            ]

            if len(linked_vars) != 1:
                violations.append(
                    f"Literal '{lit_name}' in Clause '{clause_name}' must reference "
                    f"exactly one Variable (found {len(linked_vars)})."
                )
                continue

            var_obj = linked_vars[0]
            var_name = getattr(var_obj, "name_", "<unnamed>")
            var_id = _get_slot_value(var_obj, "id")
            if not isinstance(var_id, int) or isinstance(var_id, bool):
                violations.append(
                    f"Variable '{var_name}' referenced by Literal '{lit_name}' in Clause '{clause_name}' "
                    f"must have an integer attribute 'id'."
                )
                continue

            is_negated = _get_slot_value(lit_obj, "isNegated")
            if not isinstance(is_negated, bool):
                violations.append(
                    f"Literal '{lit_name}' in Clause '{clause_name}' must have a boolean attribute 'isNegated'."
                )
                continue

            pair = (var_id, is_negated)
            if pair in seen_pairs and pair not in reported_unique_vars:
                violations.append(
                    f"UniqueLiteral violated on Clause '{clause_name}': "
                    f"duplicate literal for variable id={var_id} with isNegated={is_negated}."
                )
                reported_unique_vars.add(pair)
            seen_pairs.add(pair)

            polarities = seen_polarities_by_var.setdefault(var_id, set())
            if (not is_negated) in polarities and var_id not in reported_tautology_vars:
                violations.append(
                    f"NoTautology violated on Clause '{clause_name}': "
                    f"clause contains both variable id={var_id} and its negation."
                )
                reported_tautology_vars.add(var_id)
            polarities.add(is_negated)

    return violations
