# MultiFlow

**MultiFlow is a general-purpose scheduling and constraint-arbitration engine for systems with shared resources.**

[![CI](https://github.com/TheBabelDragon/MultiFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/TheBabelDragon/MultiFlow/actions/workflows/ci.yml)

**[Live Demo](https://thebabeldragon.github.io/MultiFlow/)** · Shared resources. Competing schedules. Constraint arbitration.

Showflow proves scheduling in one domain.  
MultiFlow generalizes the scheduling substrate.  
A future quantum companion can explore alternate optimization backends.

```
             MULTIFLOW
      ┌──────────────────────┐
      │   DOMAIN INPUT       │
      │ people / machines /  │
      │ rooms / vehicles ... │
      └──────────┬───────────┘
                 ↓
      ┌──────────────────────┐
      │ NORMALIZED PROBLEM   │
      │ resources + tasks +  │
      │ constraints + goals  │
      └──────────┬───────────┘
                 ↓
      ┌──────────────────────┐
      │    SOLVER FABRIC     │
      │ classical / MILP /   │
      │ CP / quantum         │
      └──────────┬───────────┘
                 ↓
      ┌──────────────────────┐
      │     VALIDATOR        │
      │ independent truth    │
      └──────────┬───────────┘
                 ↓
      ┌──────────────────────┐
      │   ADMISSIBLE PLAN    │
      └──────────────────────┘
```

The key architectural rule:

> **MultiFlow owns the problem definition and correctness. Solvers only propose solutions.**

Infeasibility is first-class: the engine can return `NO_COMPLETE_SOLUTION` with blocking constraints and remaining capacity — it does not invent a schedule.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
PYTHONPATH=src python -m multiflow.demo.corporate
PYTHONPATH=src python -m multiflow.cli solve examples/corporate.json
PYTHONPATH=src python -m multiflow.cli solve examples/infeasible.json
```

Canonical JSON problems:

| File | Purpose |
|------|---------|
| `examples/simple.json` | Single resource, single task |
| `examples/corporate.json` | Five schedules, shared forklift/workers |
| `examples/infeasible.json` | Capacity exhaustion → `NO_COMPLETE_SOLUTION` |
| `examples/solver-benchmark.json` | Cross-backend comparison |

---

## Solver fabric

```python
from multiflow import SchedulingProblem, get_solver, Validator

problem = SchedulingProblem.from_json("examples/corporate.json")
result = get_solver("classical").solve_result(problem)
for candidate in result.candidates:
    print(Validator().validate(problem, candidate).admissible)
```

| Backend | Install | Status |
|---------|---------|--------|
| Classical | core | always available |
| CP-SAT | `pip install "multiflow[cp-sat]"` | optional OR-Tools |
| MILP | `pip install "multiflow[milp]"` | optional PuLP |
| Quantum | companion | interface → `UNAVAILABLE` |

```bash
multiflow solve examples/corporate.json --solver classical
multiflow solve examples/corporate.json --solver cp-sat
multiflow solvers
python benchmarks/compare_solvers.py examples/solver-benchmark.json
```

See [docs/solver-fabric.md](docs/solver-fabric.md).

## What MultiFlow is

- Domain-neutral resource & task model
- First-class hard and soft constraints
- Independent validator (solver cannot define correctness)
- Multi-schedule support with shared-resource arbitration
- Explanation chains on every rejection
- Pluggable solver fabric (classical / CP-SAT / MILP / quantum interface)

## License

MIT
