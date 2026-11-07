"""
Tests for T2 (Solution DSL -> BESSER quantum circuit, Grover search).

The circuits are turned into Qiskit code with BESSER's generator (T3) and run on the Aer
simulator, then compared with a brute-force (classical) check of the formula.
"""

import contextlib
import io
import itertools
import math
import os
import runpy

import pytest
from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.quantum import (
    ClassicalRegister,
    Measurement,
    PauliXGate,
    PauliZGate,
    QuantumCircuit,
    QuantumRegister,
)
from besser.generators.qiskit import QiskitGenerator

from metamodels.solution_dsl import Clause, Formula, Literal, Variable
from metamodels.solution_dsl import object_model as part1_example
from transformations.t2_solution_quantum import read_model, transform_t2_cnf_to_quantum

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class StubConfig:
    """Stands in for SolverConfig (T1 branch): same compute_grover_rounds(n)."""

    def __init__(self, num_solutions=1, grover_rounds=None):
        self.num_solutions = num_solutions
        self.grover_rounds = grover_rounds

    def compute_grover_rounds(self, n):
        if self.grover_rounds is not None:
            return self.grover_rounds
        if self.num_solutions <= 0:
            return 0
        return int(math.floor((math.pi / 4) * math.sqrt(2**n / self.num_solutions)))


def make_model(clauses):
    """Build a Solution DSL model from [[(var_id, is_negated), ...], ...]."""
    formula = Formula("f").attributes(name="test").build()
    variables = {}
    objects = {formula}
    for k, literals in enumerate(clauses):
        clause = Clause(f"c{k}").build()
        lit_objs = set()
        for j, (var_id, negated) in enumerate(literals):
            if var_id not in variables:
                variables[var_id] = Variable(f"v{var_id}").attributes(id=var_id).build()
                objects.add(variables[var_id])
            lit = Literal(f"l{k}_{j}").attributes(isNegated=negated).build()
            lit.variable = variables[var_id]
            lit_objs.add(lit)
        clause.literal = lit_objs
        clause.formula = formula
        objects |= lit_objs | {clause}
    return ObjectModel(name="test_model", objects=objects)


def run_circuit(circuit, folder, shots=1024):
    """Generate Qiskit code with BESSER, run it unchanged, return its counts."""
    with contextlib.redirect_stdout(io.StringIO()):
        QiskitGenerator(circuit, output_dir=str(folder), shots=shots).generate()
        script = runpy.run_path(
            os.path.join(str(folder), "qiskit_circuit.py"), run_name="__main__"
        )
    return script["counts"]


def formula_is_true(clauses, var_ids, assignment):
    """Classical check: every clause has at least one true literal."""
    return all(
        any(assignment[var_ids[lit["var_idx"]]] != lit["is_negated"] for lit in clause)
        for clause in clauses
    )


def all_assignments(var_ids):
    for bits in itertools.product([False, True], repeat=len(var_ids)):
        yield dict(zip(var_ids, bits))


def decode(bitstring, var_ids):
    """Qiskit writes bits right to left: the right-most character is qubit 0."""
    bits = bitstring[::-1]
    return {var_id: bits[i] == "1" for i, var_id in enumerate(var_ids)}


# Mixed negations, a 1-literal clause and a 3-literal clause:
# (x1 OR NOT x2) AND (x2 OR x3 OR NOT x4) AND (NOT x1 OR NOT x3) AND (x4)
MIXED = [
    [(1, False), (2, True)],
    [(2, False), (3, False), (4, True)],
    [(1, True), (3, True)],
    [(4, False)],
]


# ---------------------------------------------------------------------------
# Step 1 - reading the model
# ---------------------------------------------------------------------------


def test_read_model_uses_the_given_model():
    var_map, clauses = read_model(make_model(MIXED))
    var_ids = [v.id for v in var_map]
    assert var_ids == [1, 2, 3, 4]  # sorted by id

    as_pairs = sorted(
        sorted((var_ids[l["var_idx"]], l["is_negated"]) for l in c) for c in clauses
    )
    assert as_pairs == sorted(sorted(c) for c in MIXED)


def test_read_model_part1_example():
    var_map, clauses = read_model(part1_example)
    assert len(var_map) == 8
    assert len(clauses) == 8
    # c_given has a single literal (x111) - BESSER returns one object, not a set
    assert [{"var_idx": 0, "is_negated": False}] in clauses


# ---------------------------------------------------------------------------
# Step 2/3 - circuit shape
# ---------------------------------------------------------------------------


def test_registers_and_qubit_count():
    circuit, var_ids = transform_t2_cnf_to_quantum(part1_example, StubConfig())
    # The BESSER generator always writes q[...] and c[...]
    assert [r.name for r in circuit.qregs] == ["q"]
    assert [r.name for r in circuit.cregs] == ["c"]
    assert circuit.qregs[0].size == 8 + 8 + 1  # variables + clauses + target
    assert circuit.cregs[0].size == 8  # only the variables are measured
    assert var_ids == sorted(var_ids)


@pytest.mark.parametrize("rounds", [0, 1, 3])
def test_number_of_rounds_comes_from_config(rounds):
    circuit, _ = transform_t2_cnf_to_quantum(
        make_model(MIXED), StubConfig(grover_rounds=rounds)
    )
    diffusers = [op for op in circuit.operations if isinstance(op, PauliZGate)]
    assert len(diffusers) == rounds


# ---------------------------------------------------------------------------
# Step 5 - the oracle, checked on every possible input
# ---------------------------------------------------------------------------


def oracle_gates(model):
    """
    Take the oracle out of a 1-round circuit. In transform_t2_cnf_to_quantum the order is:
      n Hadamards + X + H on the target  (start)
      2 gates per clause                 (compute)
      1 gate                             (mark)
      2 gates per clause                 (uncompute)
      ... diffuser, measurements
    """
    var_map, clauses = read_model(model)
    circuit, _ = transform_t2_cnf_to_quantum(model, StubConfig(grover_rounds=1))
    start = len(var_map) + 2
    return circuit.operations[start : start + 4 * len(clauses) + 1]


def test_oracle_on_every_input(tmp_path):
    model = make_model(MIXED)
    var_map, clauses = read_model(model)
    var_ids = [v.id for v in var_map]
    n, m = len(var_ids), len(clauses)
    target = n + m

    for assignment in all_assignments(var_ids):
        qc = QuantumCircuit("oracle_test")
        qc.add_qreg(QuantumRegister("q", target + 1))
        qc.add_creg(ClassicalRegister("c", target + 1))
        for i, var_id in enumerate(var_ids):
            if assignment[var_id]:
                qc.add_operation(PauliXGate(target_qubit=i))
        # The target starts at 0 (not |->), so the oracle shows up as a bit flip.
        for gate in oracle_gates(model):
            qc.add_operation(gate)
        for q in range(target + 1):
            qc.add_operation(Measurement(target_qubit=q, output_bit=q))

        counts = run_circuit(qc, tmp_path / "oracle", shots=16)
        assert len(counts) == 1, "a fixed input must give a fixed output"
        bitstring = next(iter(counts))
        bits = bitstring[::-1]  # bits[i] is qubit i

        assert decode(bitstring, var_ids) == assignment, "variable qubits were changed"
        assert all(
            bits[q] == "0" for q in range(n, n + m)
        ), "clause qubit not put back to 0"
        expected = "1" if formula_is_true(clauses, var_ids, assignment) else "0"
        assert bits[target] == expected, f"wrong mark for {assignment}"


# ---------------------------------------------------------------------------
# Full Grover search vs. brute force
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        part1_example,
        make_model(MIXED),
        make_model(
            [[(1, True), (2, True)], [(1, False), (3, False)], [(2, False), (3, True)]]
        ),
    ],
    ids=["part1_example", "mixed_4vars", "mixed_3vars"],
)
def test_grover_finds_a_valid_solution(model, tmp_path):
    var_map, clauses = read_model(model)
    var_ids = [v.id for v in var_map]
    solutions = [
        a for a in all_assignments(var_ids) if formula_is_true(clauses, var_ids, a)
    ]

    circuit, var_ids = transform_t2_cnf_to_quantum(
        model, StubConfig(num_solutions=len(solutions))
    )
    counts = run_circuit(circuit, tmp_path / "grover", shots=1024)

    most_frequent = max(counts, key=counts.get)
    assert decode(most_frequent, var_ids) in solutions
    valid = sum(c for b, c in counts.items() if decode(b, var_ids) in solutions)
    assert valid / 1024 > 0.8, f"success probability too low: {valid / 1024:.2f}"


def test_unsatisfiable_formula_gives_no_rounds():
    model = make_model([[(1, False)], [(1, True)]])  # x1 AND NOT x1
    circuit, _ = transform_t2_cnf_to_quantum(model, StubConfig(num_solutions=0))
    assert not any(isinstance(op, PauliZGate) for op in circuit.operations)
