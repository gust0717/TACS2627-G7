"""
Solver Configuration Model (`config/solver_config.py`).

According to Lecture T6 (Slides 9, 14, 15, 22) and the Assignment specification,
solver parameters must be modelled explicitly and passed as input to T1/T2
(never hard-coded inside transformation rules).
"""

import math
from dataclasses import dataclass
from typing import Optional

SUPPORTED_ENCODINGS = {"binary"}


@dataclass
class SolverConfig:
    """Configuration parameters for T1, T2, and T3."""

    name: str = "default"
    encoding: str = "binary"
    shots: int = 1024
    num_solutions: int = 1
    grover_rounds: Optional[int] = None
    backend: str = "aer_simulator"

    def __post_init__(self) -> None:
        if self.encoding not in SUPPORTED_ENCODINGS:
            raise ValueError(
                f"Unsupported encoding {self.encoding!r}. Supported encodings: {sorted(SUPPORTED_ENCODINGS)}."
            )
        if self.shots <= 0:
            raise ValueError("shots must be a positive integer.")

    def compute_grover_rounds(self, num_variables: int) -> int:
        """
        Compute Grover iterations k = floor((pi/4) * sqrt(2^n / M))
        (Boyer et al., 1998; Lecture T6, Slide 14, Rule Q6).
        """
        if self.grover_rounds is not None:
            return self.grover_rounds
        if self.num_solutions <= 0 or num_variables <= 0:
            return 0
        return int(
            math.floor((math.pi / 4.0) * math.sqrt((2**num_variables) / self.num_solutions))
        )
