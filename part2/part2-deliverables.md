# Part II — Deliverables Reference (Transformation T1 & Classical Validation)

This document presents the technical reference for Part II of the project, covering the Model-to-Model (M2M) transformation **T1** (`Problem DSL` $\to$ `Solution DSL`), solver configuration, forward traceability, and classical 1-to-1 enumeration validation.

---

## 1. Transformation T1 Overview & Encoding Choice

Transformation **T1** (`transformations/t1_problem2solution.py`) translates a 4×4 Sudoku instance conforming to the **Problem DSL** (`metamodels/problem_dsl.py`) into a satisfiability-equivalent Conjunctive Normal Form (CNF) formula conforming to the **Solution DSL** (`metamodels/solution_dsl.py`).

### 1.1 One-Hot vs. 2-Bit Binary Encoding under the Quantum Qubit Budget

In Transformation **T2** (Lecture T6, Slide 14), the Grover oracle allocates:
- $n$ **search qubits** (one per SAT `Variable`), plus
- $m$ **clause ancilla qubits** (one per CNF `Clause`),

subject to a simulator budget of $n + m \le 20$ qubits for standard circuits (and $n \le 12$ search qubits).

| Encoding Scheme | Variables per Empty Cell | Domain Clauses per Empty Cell | Qubits for $E=1$ (`tiny`) | Qubits for $E=3$ (`medium`) |
|-----------------|--------------------------|-------------------------------|---------------------------|-----------------------------|
| **One-Hot Encoding** (Part I diagram) | $4$ ($x_{r,c,1..4}$) | $1\text{ ALO} + 6\text{ AMO} = 7$ (+ unit clues) | $4 + 10 = 14$ | $> 33$ *(exceeds budget)* |
| **2-Bit Binary Encoding + R5 Candidate Filtering** *(Selected)* | $2$ ($b_1, b_0$) | $0$ ($2^2 = 4$ matches $\{1..4\}$ bijectively) | $2 + 3 = 5$ | $6 + 10 = 16 \le 20$ |

By encoding only **empty cells** (`value is None`, `isGiven = False`) with **2 binary variables** $(b_1, b_0)$ and pruning given clues directly via 2-literal exclusions (Rule R4) before generating pairwise peer-uniqueness clauses only over common candidate values (Rule R5), T1 preserves exact 1-to-1 solution equivalence while keeping $E \in \{1, 2, 3\}$ puzzles strictly within $n + m \le 20$ qubits.

---

## 2. T1 Transformation Rules & Literature Mapping

Following the *"one function per rule"* architecture over B-UML `ObjectModel`s (Lecture T6, Slides 6, 12–14), T1 is decomposed into six deterministic rules:

| Rule | Function in `t1_problem2solution.py` | Source Concept(s) (`Problem DSL`) | Target Concept(s) (`Solution DSL` & Trace) | Transformation Logic | Literature Reference |
|------|--------------------------------------|-----------------------------------|--------------------------------------------|----------------------|----------------------|
| **R1** | `rule_r1_board_to_formula` | `Board(name, size, boxSize)` | `Formula(name="{board.name}_cnf")` | Instantiates the root CNF `Formula` container in the target `ObjectModel`. | Brambilla et al. (2017), Ch. 8–9; Lecture T6, Slide 12 |
| **R2** | `rule_r2_empty_cells_to_variables` | Empty `Cell(row=r, column=c, value=None)` | Two `Variable` objects (`var_{r}_{c}_b1`, `var_{r}_{c}_b0`) + `T1Trace` entry | Creates MSB variable `id = 100(r+1) + 10(c+1) + 1` and LSB variable `id = 100(r+1) + 10(c+1) + 0`; records `(r, c) -> [id_b1, id_b0]` in `T1Trace`. | Yato & Seta (2003); Prestwich (2009), Ch. 2; Lecture T6, Slide 12 |
| **R3** | `rule_r3_cell_domain_clauses` | Empty `Cell(r, c)`, `Board.size` | Domain validity clauses (`List[List[Tuple[int, bool]]]`) | For $4 \times 4$ Sudoku (`size = 4`), $2^2 = 4$ matches $\{1, 2, 3, 4\}$ bijectively, so no invalid bit patterns exist ($0$ clauses emitted). | Prestwich (2009), *Handbook of Satisfiability*, Ch. 2; Lecture T6, Slide 12 |
| **R4** | `rule_r4_given_clue_exclusion_clauses` | Empty `Cell(r, c)` & peer given `Cell(gr, gc, isGiven=True, value=v)` | 2-literal exclusion clauses + `allowed_values[(r, c)]` | For each distinct given value $v$ in $(r, c)$'s row, column, or 2×2 box, emits the 2-literal De Morgan clause forbidding $(r, c) = v$, leaving $\text{Allowed}(r, c) = \{1,2,3,4\} \setminus \text{Forbidden}(r, c)$. | Lynce & Ouaknine (2006); Yato & Seta (2003); Lecture T6, Slide 12 |
| **R5** | `rule_r5_peer_uniqueness_clauses` | Ordered peer pairs of empty cells $c_1 < c_2$ sharing row, column, or box | 4-literal pairwise uniqueness clauses | Deduplicates peer pairs that share both a row/column and a 2×2 box; for each $v \in \text{Allowed}(c_1) \cap \text{Allowed}(c_2)$, emits a 4-literal clause forbidding $c_1 = v \land c_2 = v$. | Yato & Seta (2003); Lynce & Ouaknine (2006); Lecture T6, Slide 12 |
| **R6** | `rule_r6_simplify_and_materialize_clauses` | Raw clause tuples from `R3 + R4 + R5` | `Clause` (`clause_k`) & `Literal` (`lit_k_j`) B-UML objects | Merges duplicate literals (`UniqueLiteral`), drops tautological clauses containing $x$ and $\neg x$ (`NoTautology`), deduplicates identical clauses, and links `Literal` $\to$ `Variable` and `Clause` $\to$ `Formula`. | Lecture T6, Slide 14; Brambilla et al. (2017), Ch. 8 |

---

## 3. Solver Configuration (`SolverConfig`) & Trace Decoding (`T1Trace`)

### 3.1 Binary Value Encoding & De Morgan Clause Polarity

For each empty cell $(r, c)$ with binary variables $(b_1, b_0)$:

$$
v = 1 + 2 \cdot \text{int}(b_1) + \text{int}(b_0) \in \{1, 2, 3, 4\}
$$

Let $d = v - 1 \in \{0, 1, 2, 3\}$ with bits $\text{bit}_1(v) = (d \gg 1) \mathbin{\&} 1$ and $\text{bit}_0(v) = d \mathbin{\&} 1$. Forbidding cell $(r, c)$ from taking value $v$ via De Morgan's law:

$$
\neg\bigl(b_1 = \text{bit}_1(v) \land b_0 = \text{bit}_0(v)\bigr) \iff (b_1 \ne \text{bit}_1(v)) \lor (b_0 \ne \text{bit}_0(v))
$$

| Value $v$ | $d = v - 1$ | Binary $(b_1, b_0)$ | 2-Literal Clause Forbidding $(r, c) = v$ | Literal Tuples `[(id_b1, isNegated), (id_b0, isNegated)]` |
|-----------|-------------|---------------------|------------------------------------------|-----------------------------------------------------------|
| $1$ | $0$ | $(0, 0)$ | $(b_1 \lor b_0)$ | `[ (id_b1, False), (id_b0, False) ]` |
| $2$ | $1$ | $(0, 1)$ | $(b_1 \lor \neg b_0)$ | `[ (id_b1, False), (id_b0, True) ]` |
| $3$ | $2$ | $(1, 0)$ | $(\neg b_1 \lor b_0)$ | `[ (id_b1, True),  (id_b0, False) ]` |
| $4$ | $3$ | $(1, 1)$ | $(\neg b_1 \lor \neg b_0)$ | `[ (id_b1, True),  (id_b0, True) ]` |

### 3.2 Solver Configuration (`config/solver_config.py`)

`SolverConfig` models all algorithm parameters outside transformation code:
- `encoding: str = "binary"`
- `shots: int = 1024`
- `num_solutions: int = 1` ($M$)
- `grover_rounds: Optional[int] = None`
- `backend: str = "aer_simulator"`

When `grover_rounds` is not manually overridden and $M > 0, n > 0$, `compute_grover_rounds(n)` computes the optimal Grover iteration count (Boyer et al., 1998; Lecture T6, Slide 14, Rule Q6):

$$
k = \left\lfloor \frac{\pi}{4}\sqrt{\frac{2^n}{M}} \right\rfloor
$$

---

## 4. Worked Example Instance (`medium`, $E = 3, M = 1$)

Consider the 4×4 `medium` puzzle with $E = 3$ empty cells at $(0, 0)$, $(0, 1)$, and $(2, 0)$:

| Row \ Column | 0 | 1 | 2 | 3 |
|--------------|---|---|---|---|
| **0** | $\_$ | $\_$ | $3$ | $4$ |
| **1** | $3$ | $4$ | $1$ | $2$ |
| **2** | $\_$ | $1$ | $4$ | $3$ |
| **3** | $4$ | $3$ | $2$ | $1$ |

1. **Rule R2 (Variables & `T1Trace`):**
   - Cell $(0, 0) \to [x_{111}, x_{110}]$ (`var_0_0_b1`, `var_0_0_b0`)
   - Cell $(0, 1) \to [x_{121}, x_{120}]$ (`var_0_1_b1`, `var_0_1_b0`)
   - Cell $(2, 0) \to [x_{311}, x_{310}]$ (`var_2_0_b1`, `var_2_0_b0`)
   - Total search variables: $n = 6$.

2. **Rule R4 (Given Clue Exclusions):**
   - Cell $(0, 0)$ sees given peers $\{3, 4\} \implies 2$ clauses: $(\neg x_{111} \lor x_{110}) \land (\neg x_{111} \lor \neg x_{110})$; $\text{Allowed}(0, 0) = \{1, 2\}$.
   - Cell $(0, 1)$ sees given peers $\{1, 3, 4\} \implies 3$ clauses: $(x_{121} \lor x_{120}) \land (\neg x_{121} \lor x_{120}) \land (\neg x_{121} \lor \neg x_{120})$; $\text{Allowed}(0, 1) = \{2\}$.
   - Cell $(2, 0)$ sees given peers $\{1, 3, 4\} \implies 3$ clauses: $(x_{311} \lor x_{310}) \land (\neg x_{311} \lor x_{310}) \land (\neg x_{311} \lor \neg x_{310})$; $\text{Allowed}(2, 0) = \{2\}$.

3. **Rule R5 (Filtered Peer Uniqueness):**
   - Peer pair $((0, 0), (0, 1))$ shares Row 0 and Box 0 with common candidate $\text{Allowed}(0, 0) \cap \text{Allowed}(0, 1) = \{2\} \implies 1$ clause forbidding both $= 2$:
     $$(x_{111} \lor \neg x_{110} \lor x_{121} \lor \neg x_{120})$$
   - Peer pair $((0, 0), (2, 0))$ shares Column 0 with common candidate $\text{Allowed}(0, 0) \cap \text{Allowed}(2, 0) = \{2\} \implies 1$ clause forbidding both $= 2$:
     $$(x_{111} \lor \neg x_{110} \lor x_{311} \lor \neg x_{310})$$

4. **Rule R6 & Decoding:**
   - Total simplified clauses: $m = 8 + 2 = 10$ ($n + m = 16 \le 20$ qubits).
   - Unique satisfying truth assignment in $\{0, 1\}^6$:
     $$\{x_{111}: 0, \; x_{110}: 0, \; x_{121}: 0, \; x_{120}: 1, \; x_{311}: 0, \; x_{310}: 1\}$$
   - Decoded via `trace.decode_assignment`:
     $$\{(0, 0): 1, \quad (0, 1): 2, \quad (2, 0): 2\}$$

---

## 5. Classical Validation Summary (`tests/test_t1.py`)

Following Lecture T6, Slide 18 (*"Testing T1: Classical Enumeration"*), `tests/classical_baseline.py` implements `solve_sudoku_brute_force(problem_model)` and `solve_sat_brute_force(solution_model)`. Across all four test categories (`tiny`, `medium`, `many`, `none`), the decoded SAT satisfying assignments match the valid Sudoku completions **1-to-1**:

| Instance | Empty Cells ($E$) | Search Variables ($n$) | CNF Clauses ($m = \|R4\| + \|R5\|$) | Total Qubits ($n + m$) | Sudoku Solutions | SAT Solutions ($M$) | Optimal Grover Iterations ($k$) | 1-to-1 Decoded Match |
|----------|-------------------|------------------------|-------------------------------------|------------------------|------------------|---------------------|---------------------------------|----------------------|
| **`tiny`** | $1$ | $2$ | $3 \;(3 + 0)$ | $5 \le 20$ | $1$ | $1$ | $1$ | Exact (`[{(0, 1): 2}]`) |
| **`medium`** | $3$ | $6$ | $10 \;(8 + 2)$ | $16 \le 20$ | $1$ | $1$ | $6$ | Exact (`[{(0, 0): 1, (0, 1): 2, (2, 0): 2}]`) |
| **`many`** | $4$ | $8$ | $16 \;(8 + 8)$ | $24 \; (n = 8 \le 12)$ | $2$ | $2$ | $8$ | Exact (both $2\times 2$ intercalate completions) |
| **`none`** | $2$ | $4$ | $8 \;(8 + 0)$ | $12 \le 20$ | $0$ | $0$ | $0$ | Exact (`[] == []`) |

> **Note on `many` ($M = 2$):** By the Latin-square intercalate property, any two distinct valid completions of a 16-cell 4×4 Sudoku board differ in at least a $2 \times 2$ combinatorial rectangle of $E = 4$ cells ($n = 8$ search qubits, $m = 8\text{ (R4)} + 8\text{ (R5)} = 16$ clauses). All instances with $E \in \{1, 2, 3\}$ (`tiny`, `none`, `medium`) require at most $16 \le 20$ total qubits.

---

## 6. Literature References

- Boyer, M., Brassard, G., Høyer, P., & Tapp, A. (1998). *Tight bounds on quantum searching*. Fortschritte der Physik, 46(4–5), 493–505.
- Brambilla, M., Cabot, J., & Wimmer, M. (2017). *Model-Driven Software Engineering in Practice* (2nd ed.). Morgan & Claypool.
- Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*. In Proceedings of the 9th International Symposium on Artificial Intelligence and Mathematics (ISAIM 2006).
- Prestwich, S. (2009). *CNF Encodings*. In Handbook of Satisfiability (pp. 75–97). IOS Press.
- Yato, T., & Seta, T. (2003). *Complexity and Completeness of Finding Another Solution and Its Application to Puzzles*. IEICE Transactions on Fundamentals of Electronics, Communications and Computer Sciences, E86-A(5), 1052–1060.
