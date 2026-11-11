"""
End-to-end demonstration pipeline (Part II).

    Problem DSL --T1--> Solution DSL (CNF) --T2--> BESSER quantum model --T3 (BESSER QiskitGenerator)-->
    Qiskit code --Aer--> counts --decode--> Sudoku cell values --> validation against the baselines

Single command (from the repository root, with the virtual environment active):

    python -m pipeline                      # all example instances
    python -m pipeline --instances small medium --repeats 5

The generated Qiskit scripts are written to `generated/<instance>/qiskit_circuit.py` and are
executed unchanged. The number of solutions M used for the Grover rounds comes from the classical
SAT baseline, never from the transformations.
"""

import argparse
import contextlib
import io
import runpy
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from besser.generators.qiskit import QiskitGenerator

from classical_baseline import solve_sat_brute_force, solve_sudoku_brute_force
from config.solver_config import SolverConfig
from examples.sudoku_instances import INSTANCES, Instance
from metamodels.problem_validator import validate_problem_model
from transformations.t1_problem2solution import UnsatisfiableProblemError, transform_t1
from transformations.t2_solution_quantum import transform_t2_cnf_to_quantum
from validation import InstanceMetrics, analyse_runs, classical_oracle_calls

Coords = Tuple[int, int]


@dataclass
class InstanceResult:
    instance: Instance
    n: int
    m: int
    qubits: int
    rounds: int
    metrics: InstanceMetrics
    quantum_solutions: List[Tuple[Dict[Coords, int], int]]  # (cells, shots)
    classical_calls: float
    seconds: float
    ok: bool
    problems: List[str]
    note: str = ""  # set when T1 already proves there is no solution, so no circuit is built


def rejected_by_t1(
    instance: Instance, baseline_sudoku: List[Dict[Coords, int]], reason: str, started: float
) -> InstanceResult:
    """Result for a puzzle where T1 finds an empty cell with no candidate value (no formula, no circuit)."""
    problems = []
    if instance.num_solutions != 0:
        problems.append(f"T1 reports no solution, expected M={instance.num_solutions}")
    if baseline_sudoku:
        problems.append("T1 reports no solution but the Sudoku baseline found one")
    return InstanceResult(
        instance=instance,
        n=0,
        m=0,
        qubits=0,
        rounds=0,
        metrics=InstanceMetrics(n=0, num_solutions=0, rounds=0, shots_total=0),
        quantum_solutions=[],
        classical_calls=0.0,
        seconds=time.time() - started,
        ok=not problems,
        problems=problems,
        note=reason,
    )


def execute_generated_code(script: Path) -> Dict[str, int]:
    """Run a generated Qiskit script unchanged and return its Aer counts."""
    with contextlib.redirect_stdout(io.StringIO()):
        namespace = runpy.run_path(str(script), run_name="__main__")
    return namespace["counts"]


def run_instance(instance: Instance, out_dir: Path, repeats: int, shots: Optional[int]) -> InstanceResult:
    started = time.time()
    problem = instance.problem_model()
    violations = validate_problem_model(problem)
    if violations:
        raise ValueError(f"{instance.name}: invalid Problem DSL model: {violations}")

    # T1: Problem DSL -> Solution DSL (CNF), plus the classical baselines
    baseline_sudoku = solve_sudoku_brute_force(problem)
    try:
        solution, trace = transform_t1(problem)
    except UnsatisfiableProblemError as error:
        return rejected_by_t1(instance, baseline_sudoku, str(error), started)
    baseline_sat = solve_sat_brute_force(solution)
    num_solutions = len(baseline_sat)  # M comes from the baseline

    # Solver configuration (modelled input of T2/T3, not hard-coded in the rules)
    config = SolverConfig(
        name=f"{instance.name}_config",
        num_solutions=num_solutions,
        shots=shots or instance.shots,
    )

    # T2: Solution DSL -> BESSER quantum model; T3: BESSER Qiskit generator
    circuit, var_ids = transform_t2_cnf_to_quantum(solution, config)
    n = len(var_ids)
    m = sum(1 for obj in solution.objects if obj.classifier.name == "Clause")
    rounds = config.compute_grover_rounds(n)
    code_dir = out_dir / instance.name
    code_dir.mkdir(parents=True, exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        QiskitGenerator(circuit, output_dir=str(code_dir), shots=config.shots).generate()
    script = code_dir / "qiskit_circuit.py"

    # Execute the generated code (several independent runs) and validate
    runs_counts = [execute_generated_code(script) for _ in range(repeats)]
    metrics = analyse_runs(runs_counts, var_ids, baseline_sat, n, rounds)

    # Decode the measured solutions back to Sudoku cells through the T1 trace
    by_true_vars = {frozenset(v for v, b in a.items() if b): a for a in baseline_sat}
    quantum_solutions = [
        (trace.decode_assignment(by_true_vars[key]), shots_)
        for key, shots_ in sorted(metrics.solution_counts.items(), key=lambda item: -item[1])
    ]

    problems = []
    if num_solutions != instance.num_solutions:
        problems.append(f"baseline M={num_solutions}, expected {instance.num_solutions}")
    if len(baseline_sudoku) != num_solutions:
        problems.append("Sudoku baseline and SAT baseline disagree on M")
    if any(cells not in baseline_sudoku for cells, _ in quantum_solutions):
        problems.append("a measured solution is not a Sudoku solution")
    if num_solutions > 0 and not metrics.matches_theory:
        problems.append(
            f"P measured {metrics.p_measured:.3f} differs from theory {metrics.p_theory:.3f}"
        )
    if num_solutions == 0 and metrics.solution_shots != 0:
        problems.append("a solution was measured although M=0")

    return InstanceResult(
        instance=instance,
        n=n,
        m=m,
        qubits=circuit.num_qubits,
        rounds=rounds,
        metrics=metrics,
        quantum_solutions=quantum_solutions,
        classical_calls=classical_oracle_calls(n, num_solutions),
        seconds=time.time() - started,
        ok=not problems,
        problems=problems,
    )


def format_board(grid: List[List[int]], cells: Dict[Coords, int]) -> List[str]:
    """Rows of the board; cells filled by the quantum search are shown in brackets."""
    return [
        " ".join(f"[{cells[(r, c)]}]" if (r, c) in cells else f" {v or '_'} " for c, v in enumerate(row))
        for r, row in enumerate(grid)
    ]


def print_result(result: InstanceResult) -> None:
    inst, mt = result.instance, result.metrics
    print(f"\n=== {inst.name}: {inst.description}")
    if result.note:
        print(f"  no solution, detected by T1 before any circuit is built: {result.note}")
        print(f"  validation: {'OK' if result.ok else 'FAILED - ' + '; '.join(result.problems)}")
        return
    print(
        f"  CNF: n={result.n} variables, m={result.m} clauses; circuit: {result.qubits} qubits; "
        f"baseline M={mt.num_solutions}; Grover rounds k={result.rounds}"
    )
    if result.quantum_solutions:
        for cells, shots_ in result.quantum_solutions:
            print(f"  measured solution ({shots_}/{mt.shots_total} shots):")
            for line in format_board(inst.grid, cells):
                print(f"    {line}")
    elif mt.num_solutions == 0:
        print("  no satisfying outcome measured (the baseline confirms the puzzle has no solution)")
    else:
        print("  no satisfying outcome measured")
    print(
        f"  P(solution): measured {mt.p_measured:.3f} vs theory {mt.p_theory:.3f} (tol {mt.p_tolerance:.3f}); "
        f"success rate (top outcome is a solution) "
        f"{'n/a (M=0)' if mt.num_solutions == 0 else f'{mt.top1_successes}/{mt.runs}'}"
    )
    print(
        f"  oracle calls: Grover {result.rounds} vs classical scan ~{result.classical_calls:.1f} "
        f"formula evaluations; time {result.seconds:.1f}s"
    )
    print(f"  validation: {'OK' if result.ok else 'FAILED - ' + '; '.join(result.problems)}")


def write_summary(results: List[InstanceResult], path: Path) -> None:
    rows = [
        "| Instance | n | m | Qubits | M | k | P measured | P theory | Success rate | Grover calls | Classical calls | Valid |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        mt = r.metrics
        if r.note:  # rejected by T1: nothing was built or measured
            valid = "yes" if r.ok else "NO"
            rows.append(f"| {r.instance.name} | - | - | - | 0 | - | - | - | n/a | - | - | {valid} (no solution, detected by T1) |")
            continue
        rows.append(
            f"| {r.instance.name} | {r.n} | {r.m} | {r.qubits} | {mt.num_solutions} | {r.rounds} | "
            f"{mt.p_measured:.3f} | {mt.p_theory:.3f} | {'n/a' if mt.num_solutions == 0 else f'{mt.top1_successes}/{mt.runs}'} | {r.rounds} | "
            f"{r.classical_calls:.1f} | {'yes' if r.ok else 'NO'} |"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Sudoku -> CNF -> Grover (BESSER/Qiskit) demonstration")
    parser.add_argument("--instances", nargs="*", help="instance names (default: all)")
    parser.add_argument("--repeats", type=int, default=3, help="independent runs per instance (default 3)")
    parser.add_argument("--shots", type=int, default=None, help="override the shots of each instance")
    parser.add_argument("--out", default="generated", help="directory for generated code and summary")
    args = parser.parse_args(argv)

    by_name = {inst.name: inst for inst in INSTANCES}
    names = args.instances or list(by_name)
    unknown = [name for name in names if name not in by_name]
    if unknown:
        parser.error(f"unknown instances {unknown}; available: {list(by_name)}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for name in names:
        result = run_instance(by_name[name], out_dir, args.repeats, args.shots)
        print_result(result)
        results.append(result)
    write_summary(results, out_dir / "summary.md")
    print(f"\nSummary table: {out_dir / 'summary.md'}")
    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
