"""
Python OCL validator for the Solution DSL (SAT / CNF formula).

The metamodel itself lives in `metamodels/solution_dsl.py`, which is the
unmodified B-UML export produced by BESSER from `part1/Sudoku Solution DSL.json`.
This module only adds the Python check of its OCL invariants (Lecture T6, Slide 20),
kept separate so the generated file can be re-exported from BESSER without edits.
"""

from besser.BUML.metamodel.object import ObjectModel

from metamodels.solution_dsl import Clause, Formula, Literal_Clause, Literal_Variable


def _end(association, name: str):
    """Return the end called `name` of a BESSER association."""
    return next(end for end in association.ends if end.name == name)


# Association ends used to navigate links; matched by identity, never by name.
CLAUSE_TO_LITERAL = _end(Literal_Clause, "literal")
LITERAL_TO_VARIABLE = _end(Literal_Variable, "variable")


def _get_slot_value(obj, attr_name: str):
    """Return the primitive value stored in `obj`'s slot for `attr_name`, or None if unset."""
    for slot in getattr(obj, "slots", []):
        if getattr(slot.attribute, "name", None) == attr_name:
            return slot.value.value
    return None


def _linked(obj, association_end) -> list:
    """Objects linked to `obj` through `association_end`."""
    return [le.object for le in obj.link_ends() if le.association_end is association_end]


def validate_solution_model(model: ObjectModel) -> list[str]:
    """
    Validate a Solution DSL object model.

    Checks:
      - Model contains at least one Formula and at least one Clause.
      - Structure, via BESSER's `ObjectModel.validate()`: every multiplicity
        (Clause in exactly one Formula, Literal in exactly one Clause, Literal
        references exactly one Variable), link types, and links to objects
        outside the model.
      - Every Formula has a non-empty `name`, every Literal a boolean `isNegated`
        and every referenced Variable an integer `id`.
      - ClauseNotEmpty: every Clause has at least one Literal.
      - UniqueLiteral: no Clause has two literals with the same variable and polarity.
      - NoTautology: no Clause contains a literal and its negation.

    UniqueLiteral and NoTautology compare variables by `Variable.id`, not by object
    identity as the OCL does. This is deliberately stricter: an id encodes one
    (row, column, value) triple, so two Variable objects with the same id are the
    same Boolean variable.

    Returns:
        A list of violation messages (empty list if valid).
    """
    violations: list[str] = []

    objects = model.objects or set()
    formulas = [obj for obj in objects if obj.classifier is Formula]
    clauses = [obj for obj in objects if obj.classifier is Clause]

    if not formulas:
        violations.append("Model contains no Formula object.")
    if not clauses:
        violations.append("Model contains no Clause objects.")

    violations.extend(model.validate(raise_exception=False)["errors"])

    for formula_obj in sorted(formulas, key=lambda o: o.name_):
        formula_name_val = _get_slot_value(formula_obj, "name")
        if not isinstance(formula_name_val, str) or not formula_name_val.strip():
            violations.append(
                f"Formula '{formula_obj.name_}' must have a non-empty string attribute 'name'."
            )

    for clause_obj in sorted(clauses, key=lambda o: o.name_):
        clause_name = clause_obj.name_
        clause_literals = _linked(clause_obj, CLAUSE_TO_LITERAL)

        if not clause_literals:
            violations.append(
                f"ClauseNotEmpty violated on Clause '{clause_name}': clause must contain at least one literal."
            )
            continue

        seen_polarities_by_var: dict[int, set[bool]] = {}
        seen_pairs: set[tuple[int, bool]] = set()
        reported_unique_vars: set[tuple[int, bool]] = set()
        reported_tautology_vars: set[int] = set()

        for lit_obj in sorted(clause_literals, key=lambda o: o.name_):
            lit_name = lit_obj.name_
            linked_vars = _linked(lit_obj, LITERAL_TO_VARIABLE)
            if len(linked_vars) != 1:
                continue  # multiplicity already reported by model.validate()

            var_obj = linked_vars[0]
            var_id = _get_slot_value(var_obj, "id")
            if not isinstance(var_id, int) or isinstance(var_id, bool):
                violations.append(
                    f"Variable '{var_obj.name_}' referenced by Literal '{lit_name}' in Clause '{clause_name}' "
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
