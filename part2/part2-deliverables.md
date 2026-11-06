# Part II — Deliverables Reference

---

## 1. M2M Transformations

Each transformation follows the *"one function per rule"* pattern over B-UML `ObjectModel`s (Lecture T6, Slides 6, 12–14).

### 1.1 T1: Problem DSL → Solution DSL

T1 (`transformations/t1_problem2solution.py`) translates a 4×4 Sudoku (`metamodels/problem_dsl.py`) into a CNF formula with exactly the same solutions (`metamodels/solution_dsl.py`).

#### Encoding

T1 keeps the Part I encoding: one Boolean variable $x_{r,c,v}$ per (row, column, value), meaning "cell $(r, c)$ holds value $v$", with id

$$
\text{id}(x_{r,c,v}) = 100(r+1) + 10(c+1) + v
$$

so 111 means "cell (0,0) holds 1". The full board would need $16 \times 4 = 64$ variables and hundreds of clauses. The Grover oracle needs one qubit per variable ($n$) plus one ancilla per clause ($m$), and the simulator handles roughly $n + m \approx 20$. T1 therefore only creates the variables a puzzle needs:

1. **Given cells get no variables.** Their value is already known.
2. **Values used by a given peer are pruned.** An empty cell only gets variables for its *candidate* values: those not used by a given cell in its row, column or 2×2 box. If an empty cell has no candidate left, the puzzle has no solution and T1 raises `UnsatisfiableProblemError`.

A 2-bit binary encoding ($v = 1 + 2b_1 + b_0$) was also evaluated. It needs no exactly-one clauses, but always costs 2 variables per empty cell, while after pruning most cells have only 1–2 candidates:

| Instance | Binary $n + m$ | Pruned one-hot $n + m$ (selected) |
|---|---|---|
| `tiny` (1 empty cell) | 5 | 2 |
| `medium` (3 empty cells) | 16 | 10 |
| `many` (4 empty cells) | 24 | 24 |

#### Rules

A cell is a clue when its `value` is defined; empty cells have no `value`. $\text{Cand}(c)$ is the set of candidate values of empty cell $c$.

| Rule | Function | Mapping | Reference |
|---|---|---|---|
| **R1** | `rule_r1_board_to_formula` | `Board` → `Formula` named `{board}_cnf` | Brambilla et al. (2017), Ch. 8–9 |
| **R2** | `rule_r2_candidate_values` | empty `Cell` → $\text{Cand}(c) = \lbrace 1,2,3,4 \rbrace \setminus$ values of its given peers | Lynce & Ouaknine (2006) |
| **R3** | `rule_r3_candidates_to_variables` | (empty `Cell`, candidate $v$) → `Variable` with the id above, recorded in `T1Trace` | Lynce & Ouaknine (2006) |
| **R4** | `rule_r4_exactly_one_value_clauses` | empty `Cell` → at least one candidate $\bigvee_v x_{c,v}$, and at most one: $\neg x_{c,v} \lor \neg x_{c,w}$ for each pair $v \neq w$ | Prestwich (2009), Ch. 2 |
| **R5** | `rule_r5_peer_uniqueness_clauses` | pair of empty peers $c, d$ → $\neg x_{c,v} \lor \neg x_{d,v}$ for each $v$ in $\text{Cand}(c) \cap \text{Cand}(d)$ | Lynce & Ouaknine (2006) |
| **R6** | `rule_r6_simplify_and_materialize_clauses` | raw clauses → `Clause` and `Literal` objects, after merging duplicate literals (`UniqueLiteral`), dropping tautologies (`NoTautology`) and removing repeated clauses | Lecture T6, Slide 14 |

#### Trace

`T1Trace.cell_to_vars[(r, c)]` maps each candidate value to its variable id. `decode_assignment` reads the single true variable of each empty cell and returns `{(r, c): v}`; an assignment with zero or several true variables for a cell is rejected.

#### Worked example (`medium`)

```
 .  .  3  4
 3  4  1  2
 .  1  4  3
 4  3  2  1
```

1. **R2:** cell (0,0) sees 3 and 4, so its candidates are 1 and 2. Cells (0,1) and (2,0) see 1, 3 and 4, so their only candidate is 2.
2. **R3:** variables $x_{111}, x_{112}, x_{122}, x_{312}$, so $n = 4$.
3. **R4:** $(x_{111} \lor x_{112})$, $(\neg x_{111} \lor \neg x_{112})$, $(x_{122})$, $(x_{312})$.
4. **R5:** (0,0) and (0,1) share row 0 and can both be 2: $(\neg x_{112} \lor \neg x_{122})$. (0,0) and (2,0) share column 0: $(\neg x_{112} \lor \neg x_{312})$. (0,1) and (2,0) are not peers.
5. **R6:** $m = 6$ clauses, so $n + m = 10$ qubits. The only satisfying assignment sets $x_{111}, x_{122}, x_{312}$ true, which decodes to (0,0) = 1, (0,1) = 2, (2,0) = 2.

---

## 2. Validation Against the Classical Baseline

`tests/classical_baseline.py` provides two classical solvers (Lecture T6, Slide 18):

- `solve_sudoku_brute_force` tries every value in the empty cells and keeps the valid grids. It does not use the SAT encoding, so it is an independent reference.
- `solve_sat_brute_force` lists every satisfying assignment of T1's formula with the Glucose SAT solver from PySAT (Ignatiev et al., 2018).

The tests in `tests/test_t1.py` check that the decoded SAT solutions equal the Sudoku solutions exactly:

| Instance | Empty cells | Variables $n$ | Clauses $m$ | Qubits $n + m$ | Solutions $M$ |
|---|---|---|---|---|---|
| `tiny` | 1 | 1 | 1 | 2 | 1 |
| `medium` | 3 | 4 | 6 | 10 | 1 |
| `many` | 4 | 8 | 16 | 24 | 2 |
| `none` | 4 | 4 | 6 | 10 | 0 |

- **`many`:** two different solutions of a 4×4 Sudoku differ in at least a 2×2 rectangle of 4 cells, each with 2 candidates. This gives $n = 8$ and $m = 16$, the smallest multi-solution instance for this encoding, slightly above the ~20-qubit guideline.
- **`none`:** every empty cell keeps one candidate, but (1,2) and (2,2) must both be 1, and (0,3) and (3,3) must both be 2, so no solution exists.
- **No candidate left:** a puzzle where an empty cell's peers already use 1, 2, 3 and 4 is rejected by R2 with `UnsatisfiableProblemError`.
- **Exhaustive check:** each of the 120 ways to blank two cells of a solved grid gives a 1-to-1 match.

---

## 3. References

- Brambilla, M., Cabot, J., & Wimmer, M. (2017). *Model-Driven Software Engineering in Practice* (2nd ed.). Morgan & Claypool.
- Ignatiev, A., Morgado, A., & Marques-Silva, J. (2018). *PySAT: A Python Toolkit for Prototyping with SAT Oracles*. In Theory and Applications of Satisfiability Testing (SAT 2018), LNCS 10929, 428–437.
- Lynce, I., & Ouaknine, J. (2006). *Sudoku as a SAT Problem*. In Proceedings of the 9th International Symposium on Artificial Intelligence and Mathematics (ISAIM 2006).
- Prestwich, S. (2009). *CNF Encodings*. In Handbook of Satisfiability (pp. 75–97). IOS Press.
