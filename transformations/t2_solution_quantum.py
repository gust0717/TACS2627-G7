from besser.BUML.metamodel.quantum import (
    QuantumCircuit,
    QuantumRegister,
    ClassicalRegister,
    HadamardGate,
    PauliXGate,
    PauliZGate,
    Measurement,
    ControlState,
)

from metamodels.solution_validator import validate_solution_model


def read_model(model):  # Read the model into plain python lists
    # 1. Collect all unique variables and map them to circuit qubit indices
    variables = [obj for obj in model.objects if obj.classifier.name == "Variable"]
    # Sort variables by ID
    sorted_vars = sorted(variables, key=lambda v: v.id)
    var_map = {var: idx for idx, var in enumerate(sorted_vars)}

    # 2. Collect all clauses, sorted by name (model objects are stored in a set, which has no order)
    clauses = sorted(
        [obj for obj in model.objects if obj.classifier.name == "Clause"],
        key=lambda c: c.name_,
    )

    # 3. Parse clause literals
    parsed_clauses = []
    for clause in clauses:
        # Check if clause.literal is a set/list or single object
        lits = (
            clause.literal
            if isinstance(clause.literal, (set, list))
            else {clause.literal}
        )
        clause_info = []
        for lit in lits:
            clause_info.append(
                {"var_idx": var_map[lit.variable], "is_negated": lit.isNegated}
            )
        parsed_clauses.append(clause_info)

    return var_map, parsed_clauses


def rule_q1_init(var_qubits, target_qubit):
    gates = [HadamardGate(target_qubit=q) for q in var_qubits]

    gates.append(PauliXGate(target_qubit=target_qubit))
    gates.append(HadamardGate(target_qubit=target_qubit))

    return gates


def rule_q2_compute_clause(clause, clause_ancilla, var_qubits):
    ctrl_qubits = [var_qubits[lit["var_idx"]] for lit in clause]
    ctrl_states = [
        ControlState.CONTROL if lit["is_negated"] else ControlState.ANTI_CONTROL
        for lit in clause
    ]

    return [
        PauliXGate(
            target_qubit=clause_ancilla,
            control_qubits=ctrl_qubits,
            control_states=ctrl_states,
        ),
        PauliXGate(target_qubit=clause_ancilla),
    ]


def rule_q3_mark(clause_qubits, target_qubit):
    return [PauliXGate(target_qubit=target_qubit, control_qubits=clause_qubits)]


def rule_q4_uncompute_clause(clause, clause_ancilla, var_qubits):
    return list(reversed(rule_q2_compute_clause(clause, clause_ancilla, var_qubits)))


def build_oracle(clauses, var_qubits, clause_qubits, target_qubit):
    gates = []

    for clause, ancilla in zip(clauses, clause_qubits):
        gates += rule_q2_compute_clause(clause, ancilla, var_qubits)

    gates += rule_q3_mark(clause_qubits, target_qubit)

    for clause, ancilla in reversed(list(zip(clauses, clause_qubits))):
        gates += rule_q4_uncompute_clause(clause, ancilla, var_qubits)

    return gates


def rule_q5_diffuser(var_qubits):
    gates = []

    for q in var_qubits:
        gates += [HadamardGate(target_qubit=q), PauliXGate(target_qubit=q)]

    gates.append(
        PauliZGate(target_qubit=var_qubits[-1], control_qubits=var_qubits[:-1])
    )

    for q in var_qubits:
        gates += [PauliXGate(target_qubit=q), HadamardGate(target_qubit=q)]

    return gates


def rule_q6_measure(var_qubits):
    return [Measurement(target_qubit=q, output_bit=q) for q in var_qubits]


def transform_t2_cnf_to_quantum(
    model, config
):  # T2 Transformation: CNF Solution Model -> BESSER Quantum Model

    # 1. Check the model
    violations = validate_solution_model(model)
    if violations:
        raise ValueError("Invalid Solution DSL model: " + "; ".join(violations))

    # 2. Read the model
    var_map, clauses = read_model(model)
    num_vars = len(var_map)
    num_clauses = len(clauses)

    # 3. Qubit numbering
    var_qubits = list(range(num_vars))  # q[0 .. n-1]
    clause_qubits = list(range(num_vars, num_vars + num_clauses))  # q[n .. n+m-1]
    target_qubit = num_vars + num_clauses  # q[n+m]

    circuit = QuantumCircuit(name="Grover_Sudoku_CNF")
    circuit.add_qreg(QuantumRegister(size=target_qubit + 1, name="q"))
    circuit.add_creg(ClassicalRegister(size=num_vars, name="c"))

    def add(gates):
        for gate in gates:
            circuit.add_operation(gate)

    # 4. State Initialization
    add(rule_q1_init(var_qubits, target_qubit))

    # 5. Grover rounds: oracle + diffuser
    for _ in range(config.compute_grover_rounds(num_vars)):
        add(build_oracle(clauses, var_qubits, clause_qubits, target_qubit))
        add(rule_q5_diffuser(var_qubits))

    # 6. Measurement (one Measurement per qubit)
    add(rule_q6_measure(var_qubits))

    var_ids = [var.id for var in var_map]
    return circuit, var_ids


def decode(bitstring, var_ids):
    bits = bitstring.replace(" ", "")[::-1]

    return {var_id: bits[i] == "1" for i, var_id in enumerate(var_ids)}


def formula_is_true(clauses, var_ids, assignment):
    return all(
        any(assignment[var_ids[lit["var_idx"]]] != lit["is_negated"] for lit in clause)
        for clause in clauses
    )


def decode_counts(counts, model):
    var_map, clauses = read_model(model)
    var_ids = [var.id for var in var_map]

    for bitstring, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        assignment = decode(bitstring, var_ids)
        if formula_is_true(clauses, var_ids, assignment):
            return assignment

    return None
