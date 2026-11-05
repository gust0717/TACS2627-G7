"""
Run every example Problem DSL instance through T1 and the classical baseline.

Usage (from the repository root):  python -m examples.run_examples

For each instance it prints the board, the CNF size (n variables, m clauses),
the classical solutions, the SAT solutions decoded back to Sudoku terms, and the
optimal number of Grover iterations. T2/T3 (quantum model and Qiskit code) are
not part of this script yet.
"""

import sys

from examples.sudoku_instances import INSTANCES
from metamodels.problem_dsl import validate_problem_model
from metamodels.solution_dsl import validate_solution_model
from tests.classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force
from transformations.t1_problem2solution import transform_t1


def _count(sol_model):
    n = sum(1 for o in sol_model.objects if o.classifier.name == "Variable")
    m = sum(1 for o in sol_model.objects if o.classifier.name == "Clause")
    return n, m


def run_instance(inst) -> bool:
    problem = inst.problem_model()
    assert validate_problem_model(problem) == [], inst.name
    config = inst.solver_config()
    sol_model, trace = transform_t1(problem, config)
    assert validate_solution_model(sol_model) == [], inst.name

    n, m = _count(sol_model)
    sudoku = solve_sudoku_brute_force(problem)
    decoded = [trace.decode_assignment(a) for a in solve_sat_brute_force(sol_model)]
    ok = sudoku == decoded and len(sudoku) == inst.num_solutions

    print(f"== {inst.name}: {inst.description}")
    for row in inst.grid:
        print("   " + " ".join(str(v) if v else "_" for v in row))
    print(f"   n={n} variables, m={m} clauses, n+m={n + m} qubits (oracle with 1 ancilla/clause)")
    print(f"   classical solutions (M={len(sudoku)}): {sudoku}")
    print(f"   SAT solutions decoded:     {decoded}")
    print(f"   Grover iterations k={config.compute_grover_rounds(n)}, shots={config.shots}")
    print(f"   T1 matches baseline: {'OK' if ok else 'MISMATCH'}\n")
    return ok


if __name__ == "__main__":
    results = [run_instance(i) for i in INSTANCES]
    sys.exit(0 if all(results) else 1)
