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
# result.status is descriptive only
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
python benchmarks/compare_solvers.py examples/solver-benchmark.json
```

## Optional dependencies

Core install does **not** require OR-Tools, PuLP, or any quantum SDK.

```bash
pip install "multiflow[cp-sat]"   # OR-Tools
pip install "multiflow[milp]"     # PuLP (+ CBC)
```

## Quantum

The quantum backend is an interface only. It returns `UNAVAILABLE` until a quantum companion implements the same `Solver` contract against `SchedulingProblem` → `CandidateSolution` → Validator.

Do not claim quantum hardware execution from the core package.

## Implementing a New Solver

1. Accept `SchedulingProblem` as input.
2. Return `SolverResult` containing zero or more `CandidateSolution`s.
3. Candidates use the canonical model — no backend-specific candidate types.
4. Encode MultiFlow objectives internally; do not invent alternate objective semantics.
5. Report honest status: `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `TIME_LIMIT`, `ERROR`, `UNAVAILABLE`.
6. Never claim validity — the Independent Validator decides admissibility.
7. Register in `solver/registry.py` (explicit, not dynamic plugins).
8. Keep optional dependencies optional; report `UNAVAILABLE` when missing.
9. Add tests: same problem → candidate → Validator; invalid candidate rejected; infeasible not fabricated.

```python
from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus

class MySolver(Solver):
    name = "mine"
    version = "0.1.0"

    def solve(self, problem):
        return self.solve_result(problem).candidates

    def solve_result(self, problem) -> SolverResult:
        ...

    def metadata(self):
        return {"solverId": self.name, "solverVersion": self.version}
```
