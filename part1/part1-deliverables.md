# Part I

This document presents the deliverables of the part I of the project

## 1. Problem DSL

### 1.1 Concept List

| Concept | Intrinsic Properties | Extrinsic Properties |
|---------|----------------------|----------------------|
| **Board** | `name`: String<br>`size`: Integer<br>`boxSize`: Integer | Contains `size × size` Cells<br>`size = boxSize²` |
| **Cell** | `row`: Integer {0..size-1}<br>`column`: Integer {0..size-1}<br>`box`: Integer {0..size-1}<br>`value`: Integer {1..size} [0..1]<br>`isGiven`: Boolean | Belongs to exactly one Board<br>`box` is derived from `row` and `column`<br>`isGiven` marks a fixed clue from the initial puzzle |

#### 1.1.1 Given and Empty Cells

In the Sudoku problem, some cells are initially filled while others are empty. These filled cells are clues for the problem resolution and differently from the other cells, their values may not be changed.

We chose to add a property `isGiven` to the `Cell` class in order to capture this concept and differentiate the types of cells, so that:

- a fixed clue: `value` is defined, `isGiven = true`, and the value belongs to `{1..size}`
- an empty cell: `value` is undefined and `isGiven = false`
- a filled but non-given cell: `value` is defined after solving, while `isGiven = false`

Or in other words:

- if `isGiven = true`, the value is part of the initial puzzle and must not be changed
- if `isGiven = false` and `value` is defined, the value was derived during solving
- if `value` is absent, the cell is still a valid board position but is currently unassigned

### 1.2 Metamodel

![Sudoku problem metamodel](Sudoku%20Problem%20Metamodel.png)

Figure 1: Sudoku problem metamodel created in BESSER.

The following diagram displays the class diagram created in Besser in order to represent the metamodel of the problem.

The implementation of the metamodel can be found in `Sudoku Problem DSL.py` and `Sudoku Problem DSL.json`.

### 1.3 OCL Constraints

Here follows the list of OLC constraints inserted into the model (grouped by context):

```ocl
context Board
inv BoxSizePositive: self.boxSize >= 1
inv SizeConsistent: self.size = self.boxSize * self.boxSize
inv CellCount: self.cell->size() = self.size * self.size
inv UniquePositions: self.cell->forAll(c1, c2 | c1 <> c2 implies (c1.row <> c2.row or c1.column <> c2.column))
inv ConsistentValues: self.cell->forAll(c1, c2 | (c1 <> c2 and not c1.value.oclIsUndefined() and not c2.value.oclIsUndefined() and (c1.row = c2.row or c1.column = c2.column or c1.box = c2.box)) implies c1.value <> c2.value)

context Cell
inv PositionValid: self.row >= 0 and self.row < self.board.size and self.column >= 0 and self.column < self.board.size 
inv BoxCoherent: self.box = (self.row / self.board.boxSize).floor() * self.board.boxSize + (self.column / self.board.boxSize).floor()
inv GivenFlagValid: self.isGiven = True or self.isGiven = False
inv ValueValid: self.value.oclIsUndefined() or (self.value >= 1 and self.value <= self.board.size)
```

| Constraint | Rule it enforces |
|------------|------------------|
| `BoxSizePositive`, `SizeConsistent` | `size = boxSize²` |
| `CellCount`, `UniquePositions` | exactly one Cell per grid position |
| `ConsistentValues` | given values never repeat in a row, column or box |
| `PositionValid` | `row`, `column` in `{0..size-1}` |
| `BoxCoherent` | `box` agrees with `row` and `column` |
| `GivenFlagValid` | `isGiven` is a boolean marker for fixed puzzle clues |
| `ValueValid` | `value`, if present, in `{1..size}` |

## 1.4 Example Model for Problem Instance

A very simple valid problem instance is the 4x4 Sudoku board with `size = 4` and `boxSize = 2`. This board has 16 positions, grouped into 4 boxes of 2x2 cells (from 0 to 3).

A minimal example is:

| Row \ Column | 0 | 1 | 2 | 3 |
|--------------|---|---|---|---|
| 0 | 1 |  |  |  |
| 1 |  |  | 2 |  |
| 2 |  | 3 |  |  |
| 3 |  |  |  | 4 |

This corresponds to the following givens:

- `(0,0)` has value `1`
- `(1,2)` has value `2`
- `(2,1)` has value `3`
- `(3,3)` has value `4`

All other cells are empty, represented by an undefined `value`. The board is still valid because the given values are not repeated in the same row, column or 2x2 box, and the board respects the structural rules of the model.

With our metamodel, this problem instance can be represented by the following Besser object diagram:

![Sudoku problem instance](Sudoku%20Problem%20Instance.png)

Figure 2: Example Sudoku problem instance represented as a BESSER object diagram.

---


## 2. Solution DSL

### 2.1 Concept List

| Concept | Intrinsic Properties | Extrinsic Properties |
|---------|----------------------|----------------------|
| **Formula** | `name`: String | Contains Clauses; holds the conjunction ($\bigwedge$) of all clauses in the CNF formula |
| **Clause** | *(none)* | Belongs to a Formula; contains Literals; holds the disjunction ($\bigvee$) of all its literals |
| **Literal** | `isNegated`: Boolean | Belongs to a Clause; references a Variable; represents a variable or its negation |
| **Variable** | `id`: Integer | Referenced by Literals; represents a unique Boolean variable whose `id` encodes cell $(r, c)$ and candidate value $v$ via $100(r+1) + 10(c+1) + v$ (e.g., $111$ for cell $(0,0)=1$) |

### 2.2 Metamodel

![Sudoku Solution Metamodel](Sudoku%20Solution%20Metamodel.png)

### 2.3 OCL Constraints

| Constraint | Rule it enforces |
|------------|------------------|
| `ClauseNotEmpty` | A clause must contain at least one literal |
| `UniqueLiteral` | No duplicate literals within a clause |
| `NoTautology` | No complementary literals ($x$ and $\neg x$) within a clause |

```ocl
context Clause
inv ClauseNotEmpty:
  self.literal->size() > 0

inv UniqueLiteral:
  self.literal->forAll(l1, l2 | 
    l1 <> l2 implies (l1.variable <> l2.variable or l1.isNegated <> l2.isNegated)
  )

inv NoTautology: 
  self.literal->forAll(l1, l2 | 
    (l1 <> l2 and l1.variable = l2.variable) 
    implies l1.isNegated = l2.isNegated
  )
```

## 2.4 Example Model for Solution Instance

To keep the diagram readable and avoid excessive visual complexity, this example only models the constraints for `cell(0,0)`. In a complete solution model, the same pattern applied here must be repeated for all remaining cells across the board.

The following CNF formula $\Phi$ captures these constraints:

$$
\begin{aligned}
\Phi = & \underbrace{(x_{111})}_{\text{Given Clue}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{121}) \land (\neg x_{111} \lor \neg x_{131}) \land (\neg x_{111} \lor \neg x_{141})}_{\text{Row 0 Uniqueness}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{211}) \land (\neg x_{111} \lor \neg x_{311}) \land (\neg x_{111} \lor \neg x_{411})}_{\text{Column 0 Uniqueness}} \\
& \land \underbrace{(\neg x_{111} \lor \neg x_{221})}_{\text{Box 0 Uniqueness}}
\end{aligned}
$$

This formula is represented in the solution instance diagram below:

![Sudoku Solution Instance](Sudoku%20Solution%20Instance.png)