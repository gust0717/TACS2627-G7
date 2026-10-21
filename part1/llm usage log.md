# LLM Usage Log

Here we explain the main usages of LLM by the group in the development of the project part I.

Firstly, LLMs were used overall as a means of text revision and improvement.

In the development of the Problem DSL, LLMs were used:
* To validate the metamodel created by the group: the group discussed and created the metamodel in BESSER. Then we used Claude to analyse and validate if the model created was correct and sufficient to represent the Sudoku problem.
* To create the OCL constraints: with the metamodel in BESSER, we passed the constraints we envisioned for the problem to Claude in order to translate them to the OCL notation, which was then included in the BESSER metamodel.
* To write the problem instance: given the metamodel, the group specified a simple problem instance to a LLM (Copilot), which then wrote the text, which was reviewed by the group.

In the development of the Solution DSL, LLMs were used:
* To understand the CNF formula: LLMs were used to study how the CNF formulas work and how the group could implement them
* To create the Solution Metamodel in BESSER: the team first created the Solution Metamodel in draw.io. Then we used LLMs in order to convert said metamodel into a JSON that could be imported into BESSER, where the group would finalize the metamodel.
* To create the OCL constraints: with the metamodel in BESSER, the team used LLMs in order to develop the OCL constraints of the solution metamodel, which were then added to metamodel.