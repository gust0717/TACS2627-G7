import math

import pytest

from validation import classical_oracle_calls, theoretical_probability


def test_theoretical_probability():
    assert theoretical_probability(1, 1, 1) == pytest.approx(0.5)  # N=2, M=1: no amplification possible
    assert theoretical_probability(8, 1, 12) == pytest.approx(0.9999, abs=1e-3)
    assert theoretical_probability(4, 1, 3) == pytest.approx(math.sin(7 * math.asin(0.25)) ** 2)
    assert theoretical_probability(4, 0, 0) == 0.0


def test_classical_oracle_calls():
    assert classical_oracle_calls(4, 1) == pytest.approx(8.5)
    assert classical_oracle_calls(4, 0) == 16.0
