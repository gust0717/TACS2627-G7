"""
Problem DSL — Sudoku 4x4 Metamodel & OCL Constraints (`metamodels/problem_dsl.py`).

Refactored from Part I (`part1/Sudoku Problem DSL.py`) following Lecture T6, Slide 22.
"""

from typing import Optional

from besser.BUML.metamodel.object import ObjectModel
from besser.BUML.metamodel.structural import (
    BinaryAssociation,
    BooleanType,
    Class,
    Constraint,
    DomainModel,
    IntegerType,
    Multiplicity,
    Property,
    StringType,
)

# Classes
Board = Class(name="Board")
Cell = Class(name="Cell")

# Board class attributes
Board_boxSize: Property = Property(name="boxSize", type=IntegerType)
Board_name: Property = Property(name="name", type=StringType)
Board_size: Property = Property(name="size", type=IntegerType)
Board.attributes = {Board_boxSize, Board_name, Board_size}

# Cell class attributes
Cell_box: Property = Property(name="box", type=IntegerType)
Cell_column: Property = Property(name="column", type=IntegerType)
Cell_isGiven: Property = Property(name="isGiven", type=BooleanType)
Cell_row: Property = Property(name="row", type=IntegerType)
Cell_value: Property = Property(name="value", type=IntegerType, is_optional=True)
Cell.attributes = {Cell_box, Cell_column, Cell_isGiven, Cell_row, Cell_value}

# Relationships
Cell_Board: BinaryAssociation = BinaryAssociation(
    name="Cell_Board",
    ends={
        Property(name="cell", type=Cell, multiplicity=Multiplicity(0, 9999)),
        Property(name="board", type=Board, multiplicity=Multiplicity(1, 1), is_composite=True),
    },
)

# OCL Constraints
BoxSizePositive: Constraint = Constraint(
    name="BoxSizePositive",
    context=Board,
    expression="context Board inv BoxSizePositive: self.boxSize >= 1",
    language="OCL",
    description="The size of the boxes must be positive",
)

SizeConsistent: Constraint = Constraint(
    name="SizeConsistent",
    context=Board,
    expression="context Board  inv SizeConsistent: self.size = self.boxSize * self.boxSize",
    language="OCL",
    description="The size of the board must be the sizes of the boxes squared.",
)

GivenFlagValid: Constraint = Constraint(
    name="GivenFlagValid",
    context=Cell,
    expression="context Cell inv GivenFlagValid: self.isGiven = True or self.isGiven = False",
    language="OCL",
    description="The cell must be given on not",
)

CellCount: Constraint = Constraint(
    name="CellCount",
    context=Board,
    expression="context Board inv CellCount: self.cell->size() = self.size * self.size",
    language="OCL",
    description="The amount of cells must be equal to size squared",
)

UniquePositions: Constraint = Constraint(
    name="UniquePositions",
    context=Board,
    expression=(
        "context Board inv UniquePositions: "
        "self.cell->forAll(c1, c2 | c1 <> c2 implies (c1.row <> c2.row or c1.column <> c2.column))"
    ),
    language="OCL",
    description="Each cell has an unique position",
)

ConsistentValues: Constraint = Constraint(
    name="ConsistentValues",
    context=Board,
    expression=(
        "context Board inv ConsistentValues: "
        "self.cell->forAll(c1, c2 | (c1 <> c2 and not c1.value.oclIsUndefined() and not c2.value.oclIsUndefined() "
        "and (c1.row = c2.row or c1.column = c2.column or c1.box = c2.box)) implies c1.value <> c2.value)"
    ),
    language="OCL",
    description="Different cells in the same row, column or box must have different value, as long as they are not empty",
)

PositionValid: Constraint = Constraint(
    name="PositionValid",
    context=Cell,
    expression=(
        "context Cell inv PositionValid: "
        "self.row >= 0 and self.row < self.board.size and self.column >= 0 and self.column < self.board.size"
    ),
    language="OCL",
    description="The column and row fo the cell must be valid",
)

ValueValid: Constraint = Constraint(
    name="ValueValid",
    context=Cell,
    expression="context Cell inv ValueValid: self.value.oclIsUndefined() or (self.value >= 1 and self.value <= self.board.size)",
    language="OCL",
    description="The cell value must be empty or be between 1 and board size",
)

BoxCoherent: Constraint = Constraint(
    name="BoxCoherent",
    context=Cell,
    expression=(
        "context Cell inv BoxCoherent: "
        "self.box = (self.row / self.board.boxSize).floor() * self.board.boxSize + (self.column / self.board.boxSize).floor()"
    ),
    language="OCL",
)

# Domain Model
problem_domain_model = DomainModel(
    name="Sudoku",
    types={Board, Cell},
    associations={Cell_Board},
    constraints={
        BoxSizePositive,
        SizeConsistent,
        GivenFlagValid,
        CellCount,
        UniquePositions,
        ConsistentValues,
        PositionValid,
        ValueValid,
        BoxCoherent,
    },
    generalizations=set(),
    metadata=None,
)

domain_model = problem_domain_model


def _is_strict_int(val) -> bool:
    """Return True iff `val` is an `int` and not a `bool`."""
    return isinstance(val, int) and not isinstance(val, bool)


def _get_slot_value(obj, attr_name: str):
    """Return the primitive value stored in `obj`'s slot for `attr_name`, or None if unset."""
    for slot in getattr(obj, "slots", []):
        if getattr(slot.attribute, "name", None) == attr_name:
            return slot.value.value
    return None


def _cell_coords(cell_obj) -> tuple[int, int]:
    """Return `(row, column)` coordinates of a Problem DSL `Cell` object."""
    return (int(_get_slot_value(cell_obj, "row")), int(_get_slot_value(cell_obj, "column")))


def _cell_box(cell_obj, box_size: int = 2) -> int:
    """Return the box index of a Problem DSL `Cell` object."""
    box_val = _get_slot_value(cell_obj, "box")
    if _is_strict_int(box_val):
        return box_val
    r, c = _cell_coords(cell_obj)
    return (r // box_size) * box_size + (c // box_size)


def build_sudoku_board_model(
    name: str,
    grid: list[list[Optional[int]]],
    box_size: int = 2,
) -> ObjectModel:
    """
    Construct a Problem DSL `ObjectModel` from a 2D Sudoku grid.

    Cells with `None` or `0` are treated as empty (`isGiven=False`, no `value` slot).
    Cells with an integer `>= 1` are treated as given clues (`isGiven=True`, `value=grid[r][c]`).
    """
    if not _is_strict_int(box_size) or box_size < 1:
        raise ValueError(f"box_size must be a positive integer (got {box_size!r}).")

    size = box_size * box_size
    if len(grid) != size or any(len(row) != size for row in grid):
        raise ValueError(f"grid must have dimensions {size}x{size}.")

    board_obj = Board(name).attributes(boxSize=box_size, name=name, size=size).build()
    cells = []

    for r in range(size):
        for c in range(size):
            box = (r // box_size) * box_size + (c // box_size)
            raw_val = grid[r][c]
            cell_name = f"cell_{r}_{c}"
            if raw_val is None or (_is_strict_int(raw_val) and raw_val == 0):
                cell_obj = (
                    Cell(cell_name)
                    .attributes(box=box, column=c, isGiven=False, row=r)
                    .build()
                )
            else:
                cell_obj = (
                    Cell(cell_name)
                    .attributes(box=box, column=c, isGiven=True, row=r, value=raw_val)
                    .build()
                )
            cells.append(cell_obj)

    board_obj.cell = set(cells)
    return ObjectModel(
        name=f"{name}_ObjectModel",
        objects={board_obj, *cells},
    )


def validate_problem_model(model: ObjectModel) -> list[str]:
    """
    Validate the Problem DSL OCL invariants in Python (see Lecture T6, Slide 20).

    Checks:
      - Model contains exactly one Board with a non-empty string `name`.
      - Every Cell is linked to exactly one Board (`1..1` composite association).
      - BoxSizePositive: `boxSize >= 1` (strict integer).
      - SizeConsistent: `size == boxSize * boxSize` (strict integer).
      - CellCount: `len(board.cell) == size * size`.
      - PositionValid: `0 <= row < size` and `0 <= column < size` (strict integers).
      - BoxCoherent: `box == (row // boxSize) * boxSize + (column // boxSize)` (strict integer).
      - GivenFlagValid: `isGiven` is a boolean, and if `isGiven is True`, `value` is not `None`.
      - ValueValid: `value` is `None` or a strict integer in `1..size`.
      - UniquePositions: no two distinct cells on a board share `(row, column)`.
      - ConsistentValues: no two distinct cells with defined values in the same row, column, or box share `value`.

    Returns:
        A list of violation messages (empty list if valid).
    """
    violations: list[str] = []

    objects = getattr(model, "objects", set()) or set()
    boards = [
        obj for obj in objects if getattr(getattr(obj, "classifier", None), "name", None) == "Board"
    ]
    cells = [
        obj for obj in objects if getattr(getattr(obj, "classifier", None), "name", None) == "Cell"
    ]

    if len(boards) != 1:
        violations.append(
            f"Model must contain exactly one Board object (found {len(boards)})."
        )

    for cell_obj in sorted(cells, key=lambda o: getattr(o, "name_", "")):
        cell_name = getattr(cell_obj, "name_", "<unnamed>")
        linked_boards = [
            le.object
            for le in cell_obj.link_ends()
            if (
                le.name in {"board", "board_end"}
                or getattr(le.association_end, "name", None) in {"board", "board_end"}
                or getattr(getattr(le.object, "classifier", None), "name", None) == "Board"
            )
        ]
        if len(linked_boards) != 1:
            violations.append(
                f"Cell '{cell_name}' must belong to exactly one Board (found {len(linked_boards)})."
            )

    for board_obj in sorted(boards, key=lambda o: getattr(o, "name_", "")):
        board_obj_name = getattr(board_obj, "name_", "<unnamed>")
        board_name_val = _get_slot_value(board_obj, "name")
        if not isinstance(board_name_val, str) or not board_name_val.strip():
            violations.append(
                f"Board '{board_obj_name}' must have a non-empty string attribute 'name'."
            )

        box_size = _get_slot_value(board_obj, "boxSize")
        box_size_valid = _is_strict_int(box_size) and box_size >= 1
        if not box_size_valid:
            violations.append(
                f"BoxSizePositive violated on Board '{board_obj_name}': "
                f"boxSize must be an integer >= 1 (got {box_size!r})."
            )

        size = _get_slot_value(board_obj, "size")
        size_is_int = _is_strict_int(size)
        size_valid = size_is_int and box_size_valid and size == box_size * box_size
        if not size_valid:
            violations.append(
                f"SizeConsistent violated on Board '{board_obj_name}': "
                f"size ({size!r}) must be an integer equal to boxSize * boxSize."
            )

        board_cells = sorted(
            [
                le.object
                for le in board_obj.link_ends()
                if (
                    le.name in {"cell", "cell_end"}
                    or getattr(le.association_end, "name", None) in {"cell", "cell_end"}
                    or getattr(getattr(le.object, "classifier", None), "name", None) == "Cell"
                )
            ],
            key=lambda o: getattr(o, "name_", ""),
        )

        if size_is_int and size >= 1:
            if len(board_cells) != size * size:
                violations.append(
                    f"CellCount violated on Board '{board_obj_name}': "
                    f"expected {size * size} cells, found {len(board_cells)}."
                )
        else:
            violations.append(
                f"CellCount violated on Board '{board_obj_name}': "
                f"cannot verify cell count with invalid board size ({size!r})."
            )

        seen_positions: dict[tuple[int, int], str] = {}
        reported_dup_positions: set[tuple[int, int]] = set()
        valid_cell_records: list[tuple[str, int, int, int, Optional[int]]] = []

        for cell_obj in board_cells:
            cell_name = getattr(cell_obj, "name_", "<unnamed>")
            row = _get_slot_value(cell_obj, "row")
            column = _get_slot_value(cell_obj, "column")
            box = _get_slot_value(cell_obj, "box")
            is_given = _get_slot_value(cell_obj, "isGiven")
            value = _get_slot_value(cell_obj, "value")

            row_ok = _is_strict_int(row)
            col_ok = _is_strict_int(column)
            box_ok = _is_strict_int(box)

            pos_valid = (
                row_ok
                and col_ok
                and size_is_int
                and size >= 1
                and 0 <= row < size
                and 0 <= column < size
            )
            if not pos_valid:
                violations.append(
                    f"PositionValid violated on Cell '{cell_name}': "
                    f"row ({row!r}) and column ({column!r}) must be integers in 0..{size!r}-1."
                )

            box_coherent = (
                box_ok
                and row_ok
                and col_ok
                and box_size_valid
                and box == (row // box_size) * box_size + (column // box_size)
            )
            if not box_coherent:
                violations.append(
                    f"BoxCoherent violated on Cell '{cell_name}': "
                    f"box ({box!r}) does not match (row // boxSize) * boxSize + (column // boxSize)."
                )

            if not isinstance(is_given, bool):
                violations.append(
                    f"GivenFlagValid violated on Cell '{cell_name}': "
                    f"isGiven ({is_given!r}) must be a boolean."
                )
            elif is_given is True and value is None:
                violations.append(
                    f"GivenFlagValid violated on Cell '{cell_name}': "
                    f"isGiven is True but value is undefined (None)."
                )

            val_valid = value is None or (
                _is_strict_int(value) and size_is_int and size >= 1 and 1 <= value <= size
            )
            if not val_valid:
                violations.append(
                    f"ValueValid violated on Cell '{cell_name}': "
                    f"value ({value!r}) must be None or an integer in 1..{size!r}."
                )

            if row_ok and col_ok:
                pos = (row, column)
                if pos in seen_positions and pos not in reported_dup_positions:
                    violations.append(
                        f"UniquePositions violated on Board '{board_obj_name}': "
                        f"Cells '{seen_positions[pos]}' and '{cell_name}' share position {pos}."
                    )
                    reported_dup_positions.add(pos)
                else:
                    seen_positions[pos] = cell_name

            if row_ok and col_ok and box_ok:
                valid_cell_records.append(
                    (cell_name, row, column, box, value if _is_strict_int(value) else None)
                )

        for i in range(len(valid_cell_records)):
            name_1, r1, c1, b1, v1 = valid_cell_records[i]
            if v1 is None:
                continue
            for j in range(i + 1, len(valid_cell_records)):
                name_2, r2, c2, b2, v2 = valid_cell_records[j]
                if v2 is None:
                    continue
                if (r1 == r2 or c1 == c2 or b1 == b2) and v1 == v2:
                    violations.append(
                        f"ConsistentValues violated on Board '{board_obj_name}': "
                        f"Cells '{name_1}' and '{name_2}' share a peer group and both have value {v1}."
                    )

    return violations
