"""
Validation of the quantum run against the classical baselines (Part II, deliverable 3).

Definitions (Grover; Boyer et al., 1998; Nielsen & Chuang, Ch. 6):
  N = 2^n search space, M = number of satisfying assignments (from the classical SAT baseline),
  theta = asin(sqrt(M/N)), P(k) = sin^2((2k+1) * theta) after k Grover rounds.

Metrics reported per instance:
  - probability of measuring a solution: fraction of shots whose bitstring satisfies the CNF
    (checked against the SAT baseline), compared with the theoretical P(k);
  - oracle calls: k for Grover, expected (N+1)/(M+1) formula evaluations for an unstructured
    classical scan (worst case N), N for M = 0;
  - success rate: fraction of independent runs whose most frequent outcome is a solution.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence

from transformations.t2_solution_quantum import decode


def theoretical_probability(n: int, num_solutions: int, rounds: int) -> float:
    """P(k) = sin^2((2k+1) theta) with sin(theta) = sqrt(M / 2^n); 0 when M = 0."""
    if num_solutions <= 0:
        return 0.0
    theta = math.asin(math.sqrt(num_solutions / 2**n))
    return math.sin((2 * rounds + 1) * theta) ** 2


def classical_oracle_calls(n: int, num_solutions: int) -> float:
    """Expected formula evaluations of an unstructured classical scan: (N+1)/(M+1); N if M = 0."""
    size = 2**n
    return float(size) if num_solutions <= 0 else (size + 1) / (num_solutions + 1)


def true_variables(assignment: Dict[int, bool]) -> FrozenSet[int]:
    return frozenset(var_id for var_id, value in assignment.items() if value)


@dataclass
class InstanceMetrics:
    n: int
    num_solutions: int
    rounds: int
    shots_total: int
    solution_counts: Dict[FrozenSet[int], int] = field(default_factory=dict)  # true-variable set -> shots
    solution_shots: int = 0
    top1_successes: int = 0
    runs: int = 0

    @property
    def p_measured(self) -> float:
        return self.solution_shots / self.shots_total if self.shots_total else 0.0

    @property
    def p_theory(self) -> float:
        return theoretical_probability(self.n, self.num_solutions, self.rounds)

    @property
    def success_rate(self) -> float:
        return self.top1_successes / self.runs if self.runs else 0.0

    @property
    def p_tolerance(self) -> float:
        """5 sigma of the binomial shot noise plus 0.01, for the agreement check with theory."""
        p = self.p_theory
        return 5 * math.sqrt(p * (1 - p) / self.shots_total) + 0.01 if self.shots_total else 1.0

    @property
    def matches_theory(self) -> bool:
        return abs(self.p_measured - self.p_theory) <= self.p_tolerance


def analyse_runs(
    runs_counts: Sequence[Dict[str, int]],
    var_ids: List[int],
    baseline_assignments: Sequence[Dict[int, bool]],
    n: int,
    rounds: int,
) -> InstanceMetrics:
    """
    Aggregate the Aer counts of several runs. `decode` (T2) handles Qiskit's little-endian bitstrings.
    A measured bitstring is a solution iff its true variables equal those of a baseline SAT model.
    """
    solutions = {true_variables(a) for a in baseline_assignments}
    metrics = InstanceMetrics(
        n=n,
        num_solutions=len(solutions),
        rounds=rounds,
        shots_total=sum(sum(counts.values()) for counts in runs_counts),
    )
    for counts in runs_counts:
        metrics.runs += 1
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        for bitstring, shots in counts.items():
            key = true_variables(decode(bitstring, var_ids))
            if key in solutions:
                metrics.solution_counts[key] = metrics.solution_counts.get(key, 0) + shots
                metrics.solution_shots += shots
        if ranked and true_variables(decode(ranked[0][0], var_ids)) in solutions:
            metrics.top1_successes += 1
    return metrics
