# Report Part 1 - Sudoku

**Curricular unit: TACS (Advanced Software Construction Techniques)**

**Students: Bruno Alves (up200907258), Gustavo Oliveira (up202502510), Nathália Couto (up202510623)**

**Date: 19/10/2026**

## Introduction
For this project, our problem DSL focuses on **Sudoku**, which belongs to Class B: Search with Logical Constraints. Sudoku is a traditional game based 
on numbers in which the final objective is to complete a board, to do that, the user must place each number only once per row, per column and per box, as seen in 
Image 1. The base Sudoku board is a 4x4 square, but there are many variations of the game [[1]](#1). 

<img width="1145" height="533" alt="image" src="https://github.com/user-attachments/assets/17ec27d4-0f14-4aaa-8113-9b3d1e65b966" />

*Image 1: Sudoku game*

## Problem DSL
To start the Problem DSL, we used the main book of the course, Model-Driven software engineering in practice to understand the concepts which 
lead us to the creation of the Concept list [[2]](#2). The team decided on two main classes: Board and Cell. 

**Board**

The board is the main area of the game, where it is played. The board can have multiple sizes, starting from 4, the size of the board also 
dictates the numbers, a 4x4 board can only have numbers 1-4, a 9x9 can have 1-9. A board is composed of a box of cells, and each box is a square 
of *boxSize = sqrt(size)*, that is, if I have a board with size 4, it has 4 2x2 squares inside.

**Important:** Modeling our project, we decided to go with a generic approach to adapt different Sudoku's boards sizes, but, 
in our examples and tests, we will work exclusively with a 4x4 board. After a careful consideration with professor João Pascoal,
we decided on that approach to avoid overflow problems in the Quantum phase.

**Cell**

There are size x size cells inside a Board, the traditional 4x4 has 16 cells, the cell is the area in which the player will add the numbers,
and it can start the game empty or with a given value. To support this specific rule, we added a *isGiven* parameter in the cell,
if *isGiven* is true, the cell starts the game already with a pre-assigned value (and the user cannot change it), if it is false, there is where
the player must give it a value.

**Metamodel**

The Metamodel visualization was created in BESSER, and since we used OCL in our work, the OCL 2.0 quick reference was 
used to help create and use quickly the OCL to express our constraints [[3]](#3).

For visualization of the metamodel and examples please go to the [deliverables page](https://github.com/gust0717/TACS2627-G7/blob/main/part1/part1-deliverables.md).

## Solution DSL
For the solution, we followed the Conjunctive Normal Form format, where the problem is expressed as a formula that holds the conjunction of 
all clauses [[4]](#4). 

**Variable**

Represents the unique boolean value.

To map the Sudoku cells into Boolean variables, we created a unique identification (id) based on the cell's position and value. 
A variable $x$ represents whether a specific cell $(r, c)$ contains the value $v$. 
The variable id is generated using the formula $100(r+1) + 10(c+1) + v$ (e.g., $111$ represents cell $(0,0)$ holding value $1$).

**Literal**

The Literal references a Variable, adding a boolean parameter isNegated. This allows us to 
express both positive literals ($x$) and negated literals ($\neg x$), so we can write the non-duplication rules in the clauses.

**Clause**

A Clause represents a disjunction (OR) of one or more Literals.

The Clause has some constraints that need to be followed to make sure that the generated CNF formulas are mathematically well-formed:
- *ClauseNotEmpty*:	A clause must contain at least one literal
- *UniqueLiteral*: No duplicate literals within a clause
- *NoTautology*: No complementary literals within a clause

**Formula** 

The Formula represents the root of the Solution DSL, holding the conjunction (AND) of all clauses. For the Sudoku to be solved, 
every clause in the Formula must be satisfied at the same time.

### References
<a id="1">[1]</a> [https://pt.wikipedia.org/wiki/Sudoku](https://pt.wikipedia.org/wiki/Sudoku)

<a id="2">[2]</a> Brambilla, M., Cabot, J., & Wimmer, M. (2017). Model-driven software engineering in practice. Morgan & Claypool Publishers.

<a id="3">[3]</a> [https://www.yumpu.com/s/buQVEM6xXBag1KvA](https://www.yumpu.com/s/buQVEM6xXBag1KvA)

<a id="4">[4]</a> [https://en.wikipedia.org/wiki/Conjunctive_normal_form](https://en.wikipedia.org/wiki/Conjunctive_normal_form)

