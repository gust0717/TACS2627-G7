# Report Part 2 - Sudoku

**Curricular unit: TACS (Advanced Software Construction Techniques)**

**Students: Bruno Alves (up200907258), Gustavo Oliveira (up202502510), Nathália Couto (up202510623)**

**Date:**

## 1. Introduction

![Transformation chain: metamodels (M2), models (M1) and workflow](workflow-diagram.svg)

## 2. M2M Transformations

### 2.1 T1: Problem DSL → Solution DSL

In Part I, we defined the Domain-Specific Languages (DSLs) for both the problem and solution spaces. In Part II, the goal is a transformation that bridges them. To that end, we exported the following metamodels from BESSER (B-UML):

- [`metamodels/problem_dsl.py`](../metamodels/problem_dsl.py)
- [`metamodels/solution_dsl.py`](../metamodels/solution_dsl.py)

Based on them, we created [`transformations/t1_problem2solution.py`](../transformations/t1_problem2solution.py) to transform a 4×4 Sudoku puzzle into a CNF formula. In Part I, we chose the following encoding, based on the constraints identified (excerpt for cell $(0,0)$ holding $1$):

$$
\begin{aligned}
\Phi = & \underbrace{(x_{111})}_{\text{Given Clue}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{121}) \land (\neg x_{111} \lor \neg x_{131}) \land (\neg x_{111} \lor \neg x_{141})}_{\text{Row 0 Uniqueness}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{211}) \land (\neg x_{111} \lor \neg x_{311}) \land (\neg x_{111} \lor \neg x_{411})}_{\text{Column 0 Uniqueness}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{221})}_{\text{Box 0 Uniqueness}}
\end{aligned}
$$

However, encoding every value from 1 to 4 for every cell of a 4×4 grid needs 64 variables, which is too many to simulate.

We therefore adapted the encoding to fit the qubit budget suggested in the assignment. The same variable encoding was kept: cell $(r, c)$ holding candidate value $v$ is identified by $100(r+1) + 10(c+1) + v$ (e.g., $111$ for cell $(0,0)$ holding $1$), but variables are only created for empty cells, and only for candidate values not already used by a given cell in the same row, column or box.

With this optimization, we avoid creating variables for values we already know are impossible before the formula is built. In the [example presented in Part I](../part1/Sudoku%20Problem%20Instance.png) (givens $(0,0)=1$, $(1,2)=2$, $(2,1)=3$ and $(3,3)=4$), since $(0,0)$ is given as $1$, none of its row, column or box neighbours can hold $1$, so all the Part I clauses for value $1$ disappear. The given cell itself gets no variable either, so the "Given Clue" unit clause disappears too:

| Cell      | Values still possible | Part I variable           |
|-----------|-----------------------|---------------------------|
| (0,0)     | given (1)             | ~~`var_111`~~ not created |
| (0,1)     | 2, 4                  | ~~`var_121`~~ not created |
| (0,2)     | 3, 4                  | ~~`var_131`~~ not created |
| (0,3)     | 3                     | ~~`var_141`~~ not created |
| (1,0)     | 3, 4                  | ~~`var_211`~~ not created |
| (2,0)     | 2, 4                  | ~~`var_311`~~ not created |
| (3,0)     | 2                     | ~~`var_411`~~ not created |
| (1,1)     | 4                     | ~~`var_221`~~ not created |

#### Transformation rules

T1 is implemented as one function per rule, applied in order from R1 to R6.

| Rule | Source → Target                    | Description                                                   | Reference |
|------|------------------------------------|---------------------------------------------------------------|-----------|
| R1   | `Board` → `Formula`                | One formula per puzzle                                        | [1]       |
| R2   | Empty `Cell` → candidate values    | Propagates the givens, pruning values used by peers           | [2]       |
| R3   | (Empty `Cell`, value) → `Variable` | Creates the variable and its `T1Trace` entry                  | [1], [2]  |
| R4   | Empty `Cell` → `Clause`s           | Exactly one value per cell                                    | [2]       |
| R5   | Empty peer `Cell`s → `Clause`s     | Peers never share a value                                     | [2]       |
| R6   | Clauses → `Clause`, `Literal`      | Drops duplicates/tautologies (`UniqueLiteral`, `NoTautology`) | [1]       |

The pruning described above corresponds to R2, while R4 and R5 generate the clauses of the formula.

> **Note:** Besides the CNF model, T1 outputs `T1Trace`, which maps each empty cell to its variables (e.g. cell $(0,1)$ → `var_122`, `var_124`). It is later used to decode the measured bitstrings back into Sudoku values.

### 2.2 T2: Solution DSL → Quantum DSL

With the Solution DSL ready, the next step was to create the Quantum DSL from it, this was done in steps.

#### Validate the solution model

We created a function to make sure that the solution model was well structured and that it contained all the required fields.
If some validation did not pass, the function returns a list of violations, and the transformation raises an error if the list is not empty, to stop the execution.

#### Read the solution model

We needed to read the model into Python data because the objects come without ordering, which we needed to have a deterministic qubit mapping, also, to turn object references into integer indices. 

For that, we created a function that sorts variables by id and maps them to a qubit index. Then, it sorts clauses by name and each clause becomes a list of `{var_idx, is_negated}` dicts.


#### Qubit numbering

We then create the quantum circuit. It uses a single quantum register `q` with `n + m + 1` qubits (n variables, m clauses), laid out in blocks:
- `q[0 .. n-1]`: one qubit per variable, holding the candidate assignment;
- `q[n .. n+m-1]`: one ancilla qubit per clause, holding whether that clause is satisfied;
- `q[n+m]`: the target qubit, used for the phase kickback.

We needed to place the variables first so variable `i` sits on qubit `i`, so it can be measured into classical bit `i`. The classical register has only `n` bits because the ancillas and the target are working space and will not be measured.

Finally, we decided to add a helper function to append the gates into the circuit inside the main function, so it could use the circuit directly, this also makes sure that only this function adds gates to the circuit. 

#### State Initialization

We initialize the qubits to make sure Grover’s algorithm has an unbiased starting point. For that, we use a Hadamard into every variable qubit to create an equal superposition of all assignments, the target qubit finishes at the `|−⟩` state. It runs right before the algorithm and helps to later create a phase kickback. 

#### Grover rounds

Grover's algorithm works with the amplitudes, since we initialized, every assignment has the same amplitude. Each Grover round makes the valid assignments’ amplitudes a bit larger and everyone else’s a bit smaller. After enough rounds, measuring almost surely will return a valid one.

One Grover round is composed of two steps:
- Oracle: flips the sign (phase) of valid assignments.
  - Here, we built it in three phases: compute each clause into its ancilla, mark the target with a multi-controlled X that fires only when all clauses are satisfied, and uncompute the clauses so the ancillas return to `|0⟩` and do not stay entangled with the variables. 
- Diffuser: “inversion about the mean”, which turns that sign flip into a real amplitude boost.

Every round rotates the state by a fixed angle toward the solution's direction. 

#### Measurement

Finally, we append one measurement per variable qubit, each writing into the classical bit with the same index. The process of measurement will collapse the superposition into a bitstring.

The final return is the circuit together with `var_ids` that maps each qubit position to a model variable. After execution, the measured bitstrings are decoded into assignments and checked against the clauses, because Grover's result is probabilistic. 


## 3. M2T Transformation

### 3.1 T3: Quantum DSL → Qiskit

In this process, we turned the BESSER quantum model that T2 generated into executable code, for that, we used BESSER's `QiskitGenerator`, that receives the circuit and number of shots and writes a runnable Qiskit script. 

After the generation of the script, it is executed several times on the Aer simulator, and each run produces a histogram of measured bitstrings. Each bitstring is then decoded into a variable assignment and mapped back to the Sudoku cells. Finally, the solved board is printed with the cells found by the quantum search.

To finish, the results are validated automatically to check that the measured solutions are valid Sudoku solutions, and the measured success probability matches the theoretical Grover probability for the number of solutions found by a classical baseline. A summary table with the number of variables, clauses, qubits, Grover rounds and success rates is written for each instance.

The image below shows the output for the `small` instance. The circuit has 7 qubits (3 variable qubits, 3 clause ancillas and 1 target) and runs 2 Grover rounds, since the classical baseline finds a single solution (M = 1). The solution was measured in 2909 of 3072 shots, a probability of 0.947 against the theoretical 0.945, and the cells found by the quantum search are shown in brackets.

<img src='small-instance.png' width="90%">


## 4. Workflow

As shown in section 1, the workflow is orchestrated by `pipeline.py` and it chains a set of steps in the following order:
1. Brute force on the Sudoku puzzle: get all the possible solutions for a given puzzle
2. Runs T1: converts the puzzle into a CNF formula
3. Solve that formula using PySAT: after T1, PySAT gets all the possible solutions that satisfy the CNF formula. The number of solutions **M** is stored in `SolverConfig`, which uses it to compute the number of Grover rounds $k$ (see section 2.2)
4. Runs T2: builds a quantum circuit by converting the CNF formula (generated by T1) into a quantum circuit with  $k$ Grover rounds
5. Runs T3: Besser's Qiskit generator implements that quantum circuit (generated by T2)
6. Runs Aer simulator: the `qiskit_circuit.py` generated by Besser runs on the Aer simulator and returns how many times each bitstring was measured (decoded then to CNF variables and Sudoku cells)
7. Validation against classical baseline (see section 5.2): generates a report in `generated/summary.md`

> **Note:** The whole chain runs with a single command from the repository root: `python -m pipeline`.

## 5. Validation

### 5.1 Testing

We implemented unit, integration and end-to-end tests. The integration tests are particularly important as they validate each transformation. For T1, which converts a Sudoku puzzle into a CNF formula, each test runs a solver in each of the two scopes:
- Brute force (problem scope): it tries every value in the empty cells to solve the puzzle
- PySAT (solution scope): solves the CNF formula generated by T1 and returns all possible solutions

In the end, the solutions of both scopes – problem and solution – must match. Each CNF variable is decoded to a cell (based on T1Trace), so it is possible to compare both solutions – brute force and PySAT – and validate the T1 transformation.

## 6. Limitations

During this assignment we faced the following limitations:

- We had some issues with OCL constraints defined in both metamodels as the B-OCL interpreter could not run some of them. Thus, we decided to extract them into a dedicated file for each DSL and run them as preconditions and postconditions of each transformation:
  - [`metamodels/problem_validator.py`](../metamodels/problem_validator.py)
  - [`metamodels/solution_validator.py`](../metamodels/solution_validator.py)

## References

<a id="1">[1]</a> Brambilla, M., Cabot, J., & Wimmer, M. (2017). Model-driven software engineering in practice (2nd ed.). Morgan & Claypool Publishers.

<a id="2">[2]</a> Lynce, I., & Ouaknine, J. (2006). Sudoku as a SAT problem. In Proceedings of the 9th International Symposium on Artificial Intelligence and Mathematics (ISAIM 2006).
