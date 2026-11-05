import pytest

from examples.run_examples import run_instance
from examples.sudoku_instances import INSTANCES


@pytest.mark.parametrize("inst", INSTANCES, ids=lambda i: i.name)
def test_example_instance_matches_classical_baseline(inst):
    assert run_instance(inst)
