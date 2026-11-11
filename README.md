# TACS2627-G7
Repository for the project assignment of TACS2627 (QMDE, problem B2: Sudoku 4x4, CNF + Grover).

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
.venv/bin/pytest -v
```

`requirements.txt` installs the course BESSER fork in editable mode. On Windows enable long paths first
(`git config --global core.longpaths true`), otherwise cloning the fork fails with "Filename too long".

## Demonstration (single command)

```bash
.venv/bin/python -m pipeline
```

For each example instance in `examples/sudoku_instances.py` (written in the Problem DSL) it runs
T1 (Problem DSL to CNF), T2 (CNF to BESSER quantum model), the BESSER Qiskit generator, executes the
generated code unchanged on Aer, decodes the measurements into Sudoku cells and validates them against
the classical baseline (PySAT and brute force): probability of measuring a solution (measured vs. theory
sin^2((2k+1)theta)), oracle calls (Grover k vs. classical scan) and success rate over repeated runs.

- Generated code: `generated/<instance>/qiskit_circuit.py`; summary table: `generated/summary.md`.
- All instances take about 5 minutes (`many` and `limit` need 25 qubits). A quick subset:
  `python -m pipeline --instances tiny small medium none --repeats 2`.
- Options: `--instances`, `--repeats` (default 3), `--shots`, `--out`.
