import pytest

from examples.sudoku_instances import INSTANCES, Instance
from pipeline import main, print_result, run_instance, write_summary

pytestmark = pytest.mark.e2e

FAST = [i for i in INSTANCES if i.name in {"tiny", "small", "medium", "none"}]


@pytest.mark.parametrize("inst", FAST, ids=lambda i: i.name)
def test_pipeline_end_to_end(inst, tmp_path):
    result = run_instance(inst, tmp_path, repeats=2, shots=None)
    assert result.ok, result.problems
    assert (tmp_path / inst.name / "qiskit_circuit.py").exists()
    if inst.num_solutions == 0:
        assert result.quantum_solutions == []
    else:
        assert result.metrics.p_measured > 0.4


def test_pipeline_reports_puzzle_rejected_by_t1(tmp_path, capsys):
    # (0,1) has no candidate: its row uses 1, 3, 4 and its column uses 2
    inst = Instance(
        name="no_candidate",
        description="an empty cell has no candidate value",
        grid=[
            [1, 0, 3, 4],
            [3, 2, 1, 0],
            [2, 1, 4, 3],
            [4, 3, 2, 1],
        ],
        num_solutions=0,
    )
    result = run_instance(inst, tmp_path, repeats=1, shots=None)
    assert result.ok, result.problems
    assert "Cell (0, 1) has no candidate value" in result.note
    assert result.qubits == 0 and result.quantum_solutions == []
    assert not (tmp_path / inst.name).exists()  # no circuit is generated

    print_result(result)
    assert "detected by T1" in capsys.readouterr().out
    write_summary([result], tmp_path / "summary.md")
    row = (tmp_path / "summary.md").read_text(encoding="utf-8").splitlines()[-1]
    assert row.startswith("| no_candidate | - |") and "detected by T1" in row


def test_pipeline_command_returns_success(tmp_path):
    assert main(["--instances", "small", "--repeats", "1", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "summary.md").exists()
