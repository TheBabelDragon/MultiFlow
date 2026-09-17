# Solver Fabric

MultiFlow owns the problem definition and correctness. Solvers only propose solutions.

```
SchedulingProblem
       |
       +-- Classical   (always available)
       +-- CP-SAT      (optional: pip install "multiflow[cp-sat]")
       +-- MILP        (optional: pip install "multiflow[milp]")
       +-- Quantum     (interface / companion -- UNAVAILABLE until configured)
              |
              v
       CandidateSolution
              |
              v
        Independent Validator
              |
        +-----+-----+
        v           v
   ADMISSIBLE    REJECTED
```

## Contract

```python
from multiflow import get_solver, Validator, SchedulingProblem

problem = SchedulingProblem.from_json("my_problem.json")
result = get_solver("classical").solve_result(problem)
for candidate in result.candidates:
    verdict = Validator().validate(problem, candidate)
    print(verdict.admissible, verdict.explanation_chain)
```

## CLI

```bash
multiflow solve examples/corporate.json --solver classical
multiflow solve examples/corporate.json --solver cp-sat
multiflow solve examples/corporate.json --solver milp
multiflow solve examples/corporate.json --solver quantum
multiflow solvers
```

## Optional dependencies

Core install does **not** require OR-Tools, PuLP, or any quantum SDK.

```bash
pip install "multiflow[cp-sat]"
pip install "multiflow[milp]"
```

## Quantum

The quantum backend is an interface only. It returns `UNAVAILABLE` until a quantum companion implements the same `Solver` contract.

Do not claim quantum hardware execution from the core package.
