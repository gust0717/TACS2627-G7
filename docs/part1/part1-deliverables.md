# Part I

## 1. Problem DSL

### 1.1 Concept List

| Concept | Intrinsic Properties | Extrinsic Properties |
|---------|---------------------|----------------------|
| Board   | name: String         | 4 rows, 4 columns, 4 boxes |
| Row     | index: Integer {0..3} | 4 cells |
| Column  | index: Integer {0..3} | 4 cells |
| Box     | index: Integer {0..3} | 4 cells |
| Cell    | value: Integer {1..4} [0..1] |  |

### 1.2 Metamodel

```mermaid
classDiagram
    class Board {
        +name: String
    }
    class Row {
        +index: Integer
    }
    class Column {
        +index: Integer
    }
    class Box {
        +index: Integer
    }
    class Cell {
        +value: Integer [0..1]
    }

    Board "1" *-- "4" Row
    Board "1" *-- "4" Column
    Board "1" *-- "4" Box
    Row "1" o-- "4" Cell
    Column "1" o-- "4" Cell
    Box "1" o-- "4" Cell
```
