import contextlib
import io
import itertools
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

from config.solver_config import SolverConfig
from metamodels.solution_dsl import Clause, Formula, Literal, Variable
from metamodels.solution_dsl import object_model as part1_example
from transformations.t2_solution_quantum import (
    build_oracle,
    decode,
    decode_counts,
    formula_is_true,
    read_model,
    transform_t2_cnf_to_quantum,
)


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


def all_assignments(var_ids):
    for bits in itertools.product([False, True], repeat=len(var_ids)):
        yield dict(zip(var_ids, bits))


# Mixed negations, a 1-literal clause and a 3-literal clause:
# (x1 OR NOT x2) AND (x2 OR x3 OR NOT x4) AND (NOT x1 OR NOT x3) AND (x4)
MIXED = [
    [(1, False), (2, True)],
    [(2, False), (3, False), (4, True)],
    [(1, True), (3, True)],
    [(4, False)],
]

UNSATISFIABLE = [[(1, False)], [(1, True)]]  # x1 AND NOT x1


def test_solver_config_grover_rounds():
    assert (
        SolverConfig(num_solutions=1).compute_grover_rounds(8) == 12
    )  # (pi/4)*sqrt(256)
    assert SolverConfig(num_solutions=2).compute_grover_rounds(4) == 2  # (pi/4)*sqrt(8)
    assert SolverConfig(num_solutions=0).compute_grover_rounds(8) == 0
    assert SolverConfig(grover_rounds=5).compute_grover_rounds(8) == 5  # override
    with pytest.raises(ValueError):
        SolverConfig(num_solutions=-1)
    with pytest.raises(ValueError):
        SolverConfig(grover_rounds=-1)


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


def test_empty_formula_is_rejected():
    formula = Formula("f").attributes(name="empty").build()
    empty = ObjectModel(name="empty_model", objects={formula})
    with pytest.raises(ValueError, match="no Clause"):
        transform_t2_cnf_to_quantum(empty, SolverConfig())


def test_invalid_model_is_rejected():
    # NoTautology: a clause cannot contain x1 and NOT x1
    with pytest.raises(ValueError, match="NoTautology"):
        transform_t2_cnf_to_quantum(
            make_model([[(1, False), (1, True)]]), SolverConfig()
        )


def test_registers_and_qubit_count():
    circuit, var_ids = transform_t2_cnf_to_quantum(part1_example, SolverConfig())

    assert [r.name for r in circuit.qregs] == ["q"]
    assert [r.name for r in circuit.cregs] == ["c"]
    assert circuit.qregs[0].size == 8 + 8 + 1  # variables + clauses + target
    assert circuit.cregs[0].size == 8  # only the variables are measured
    assert var_ids == sorted(var_ids)


@pytest.mark.parametrize("rounds", [0, 1, 3])
def test_number_of_rounds_comes_from_config(rounds):
    circuit, _ = transform_t2_cnf_to_quantum(
        make_model(MIXED), SolverConfig(grover_rounds=rounds)
    )
    diffusers = [op for op in circuit.operations if isinstance(op, PauliZGate)]
    assert len(diffusers) == rounds


def test_oracle_on_every_input(tmp_path):
    var_map, clauses = read_model(make_model(MIXED))
    var_ids = [v.id for v in var_map]
    n, m = len(var_ids), len(clauses)
    var_qubits = list(range(n))
    clause_qubits = list(range(n, n + m))
    target = n + m

    for assignment in all_assignments(var_ids):
        qc = QuantumCircuit("oracle_test")
        qc.add_qreg(QuantumRegister("q", target + 1))
        qc.add_creg(ClassicalRegister("c", target + 1))
        for i, var_id in enumerate(var_ids):
            if assignment[var_id]:
                qc.add_operation(PauliXGate(target_qubit=i))
        # The target starts at 0 (not |->), so the oracle shows up as a bit flip.
        for gate in build_oracle(clauses, var_qubits, clause_qubits, target):
            qc.add_operation(gate)
        for q in range(target + 1):
            qc.add_operation(Measurement(target_qubit=q, output_bit=q))

        counts = run_circuit(qc, tmp_path / "oracle", shots=16)
        assert len(counts) == 1, "a fixed input must give a fixed output"
        bitstring = next(iter(counts))
        bits = bitstring[::-1]  # bits[i] is qubit i

        assert decode(bitstring, var_ids) == assignment, "variable qubits were changed"
        assert all(
            bits[q] == "0" for q in clause_qubits
        ), "clause qubit not put back to 0"
        expected = "1" if formula_is_true(clauses, var_ids, assignment) else "0"
        assert bits[target] == expected, f"wrong mark for {assignment}"


def test_decode_is_little_endian():
    # right-most character is qubit 0 -> var_ids[0]
    assert decode("01", [7, 9]) == {7: True, 9: False}


def test_decode_counts_skips_assignments_that_break_the_formula():
    model = make_model([[(1, False)]])  # x1
    # The most frequent result breaks the formula; the valid one is returned instead.
    assert decode_counts({"0": 900, "1": 124}, model) == {1: True}


def test_decode_counts_reports_no_solution():
    model = make_model([[(1, False)]])  # x1
    assert decode_counts({"0": 1024}, model) is None


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
    config = SolverConfig(num_solutions=len(solutions))

    circuit, var_ids = transform_t2_cnf_to_quantum(model, config)
    counts = run_circuit(circuit, tmp_path / "grover", shots=config.shots)

    most_frequent = max(counts, key=counts.get)
    assert decode(most_frequent, var_ids) in solutions
    assert decode_counts(counts, model) in solutions
    valid = sum(c for b, c in counts.items() if decode(b, var_ids) in solutions)
    assert (
        valid / config.shots > 0.8
    ), f"success probability too low: {valid / config.shots:.2f}"


def test_unsatisfiable_formula_says_no_solution(tmp_path):
    model = make_model(UNSATISFIABLE)
    config = SolverConfig(num_solutions=0)
    circuit, _ = transform_t2_cnf_to_quantum(model, config)
    assert not any(isinstance(op, PauliZGate) for op in circuit.operations)  # 0 rounds

    counts = run_circuit(circuit, tmp_path / "unsat", shots=config.shots)
    assert (
        decode_counts(counts, model) is None
    )  # random bits are not decoded as an answer
