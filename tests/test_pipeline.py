import math

import pytest

from examples.sudoku_instances import INSTANCES
from pipeline import main, run_instance
from validation import classical_oracle_calls, theoretical_probability

FAST = [i for i in INSTANCES if i.name in {"tiny", "small", "medium", "none"}]


def test_theoretical_probability():
    assert theoretical_probability(1, 1, 1) == pytest.approx(0.5)  # N=2, M=1: no amplification possible
    assert theoretical_probability(8, 1, 12) == pytest.approx(0.9999, abs=1e-3)
    assert theoretical_probability(4, 1, 3) == pytest.approx(math.sin(7 * math.asin(0.25)) ** 2)
    assert theoretical_probability(4, 0, 0) == 0.0


def test_classical_oracle_calls():
    assert classical_oracle_calls(4, 1) == pytest.approx(8.5)
    assert classical_oracle_calls(4, 0) == 16.0


@pytest.mark.parametrize("inst", FAST, ids=lambda i: i.name)
def test_pipeline_end_to_end(inst, tmp_path):
    result = run_instance(inst, tmp_path, repeats=2, shots=None)
    assert result.ok, result.problems
    assert (tmp_path / inst.name / "qiskit_circuit.py").exists()
    if inst.num_solutions == 0:
        assert result.quantum_solutions == []
    else:
        assert result.metrics.p_measured > 0.4


def test_pipeline_command_returns_success(tmp_path):
    assert main(["--instances", "small", "--repeats", "1", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "summary.md").exists()
