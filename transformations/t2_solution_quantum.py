from besser.BUML.metamodel.quantum import (
    QuantumCircuit, QuantumRegister, ClassicalRegister,
    HadamardGate, PauliXGate, PauliZGate, Measurement, ControlState
)

def read_model(model): # Read the model into plain python lists
    # 1. Collect all unique variables and map them to circuit qubit indices
    variables = [obj for obj in model.objects if obj.classifier.name == "Variable"]
    # Sort variables by ID
    sorted_vars = sorted(variables, key=lambda v: v.id)
    var_map = {var: idx for idx, var in enumerate(sorted_vars)}

    # 2. Collect all clauses, sorted by name (model objects are stored in a set, which has no order)
    clauses = sorted(
        [obj for obj in model.objects if obj.classifier.name == "Clause"],
        key=lambda c: c.name_
    )

    # 3. Parse clause literals
    parsed_clauses = []
    for clause in clauses:
        # Check if clause.literal is a set/list or single object
        lits = clause.literal if isinstance(clause.literal, (set, list)) else {clause.literal}
        clause_info = []
        for lit in lits:
            clause_info.append({
                "var_idx": var_map[lit.variable],
                "is_negated": lit.isNegated
            })
        parsed_clauses.append(clause_info)

    return var_map, parsed_clauses


def transform_t2_cnf_to_quantum(model, config): # T2 Transformation: CNF Solution Model -> BESSER Quantum Model
    # 1. Read input model
    var_map, clauses = read_model(model)
    num_vars = len(var_map)
    num_clauses = len(clauses)

    # 2. Qubit numbering
    var_qubits = list(range(num_vars))                                  # q[0 .. n-1]
    clause_qubits = list(range(num_vars, num_vars + num_clauses))       # q[n .. n+m-1]
    target_qubit = num_vars + num_clauses                               # q[n+m]

    circuit = QuantumCircuit(name="Grover_Sudoku_CNF")
    circuit.add_qreg(QuantumRegister(size=target_qubit + 1, name="q"))
    circuit.add_creg(ClassicalRegister(size=num_vars, name="c"))

    # 3. State Initialization (Grover 1996; Nielsen & Chuang 6.1.1)
    for q in var_qubits:
        circuit.add_operation(HadamardGate(target_qubit=q))

    # Target qubit initialized to |-> = H(X(|0>)) 
    circuit.add_operation(PauliXGate(target_qubit=target_qubit))
    circuit.add_operation(HadamardGate(target_qubit=target_qubit))

    # 4. Grover Loop (Boyer et al. 1998)
    num_iterations = config.compute_grover_rounds(num_vars)

    for _ in range(num_iterations):
        # (De Morgan; Nielsen & Chuang 4.3, 6.1)
        for c_idx, clause in enumerate(clauses):
            clause_ancilla = clause_qubits[c_idx]
            ctrl_qubits = [var_qubits[lit["var_idx"]] for lit in clause]
            ctrl_states = [ControlState.CONTROL if lit["is_negated"] else ControlState.ANTI_CONTROL for lit in clause]

            circuit.add_operation(PauliXGate(target_qubit=clause_ancilla, control_qubits=ctrl_qubits, control_states=ctrl_states))
            circuit.add_operation(PauliXGate(target_qubit=clause_ancilla))

        # (Nielsen & Chuang 6.1.1)
        circuit.add_operation(
            PauliXGate(target_qubit=target_qubit, control_qubits=clause_qubits)
        )

        # (Bennett 1973)
        for c_idx, clause in reversed(list(enumerate(clauses))):
            clause_ancilla = clause_qubits[c_idx]
            ctrl_qubits = [var_qubits[lit["var_idx"]] for lit in clause]
            ctrl_states = [ControlState.CONTROL if lit["is_negated"] else ControlState.ANTI_CONTROL for lit in clause]

            circuit.add_operation(PauliXGate(target_qubit=clause_ancilla))
            circuit.add_operation(PauliXGate(target_qubit=clause_ancilla, control_qubits=ctrl_qubits, control_states=ctrl_states))

        # Diffuser (Grover 1996; Nielsen & Chuang 6.1.2)
        for q in var_qubits:
            circuit.add_operation(HadamardGate(target_qubit=q))
            circuit.add_operation(PauliXGate(target_qubit=q))

        circuit.add_operation(
            PauliZGate(target_qubit=var_qubits[-1], control_qubits=var_qubits[:-1])
        )

        for q in var_qubits:
            circuit.add_operation(PauliXGate(target_qubit=q))
            circuit.add_operation(HadamardGate(target_qubit=q))

    # 5. Measurement (one Measurement per qubit)
    for q in var_qubits:
        circuit.add_operation(Measurement(target_qubit=q, output_bit=q))

    var_ids = [var.id for var in var_map]
    return circuit, var_ids
