import math
from dataclasses import dataclass
from typing import Optional

@dataclass
class SolverConfig:
    # Configuration of the Grover search built by T2 and of its execution.

    name: str = "default"
    shots: int = 1024
    num_solutions: int = 1
    grover_rounds: Optional[int] = None
    backend: str = "aer_simulator"

    def __post_init__(self) -> None:
        if self.shots <= 0:
            raise ValueError("shots must be a positive integer.")
        if self.num_solutions < 0:
            raise ValueError("num_solutions cannot be negative.")
        if self.grover_rounds is not None and self.grover_rounds < 0:
            raise ValueError("grover_rounds cannot be negative.")

    def compute_grover_rounds(self, num_variables: int) -> int:
        if self.grover_rounds is not None:
            return self.grover_rounds
        if self.num_solutions <= 0 or num_variables <= 0:
            return 0
        return int(
            math.floor(
                (math.pi / 4.0) * math.sqrt((2**num_variables) / self.num_solutions)
            )
        )
