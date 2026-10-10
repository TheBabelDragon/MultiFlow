# MultiFlow

**MultiFlow is a general-purpose scheduling and constraint-arbitration engine for systems with shared resources.**

[![CI](https://github.com/TheBabelDragon/MultiFlow/actions/workflows/ci.yml/badge.svg)](https://github.com/TheBabelDragon/MultiFlow/actions/workflows/ci.yml)

**[Live Demo](https://thebabeldragon.github.io/MultiFlow/)** · Shared resources. Competing schedules. Constraint arbitration.

Showflow proves scheduling in one domain.  
MultiFlow generalizes the scheduling substrate.  
A future quantum companion can explore alternate optimization backends.

```
LIVE DOMAIN EVENTS
        ↓
  NORMALIZED STATE
        ↓
   SNAPSHOT
        ↓
 SOLVER FABRIC
        ↓
   CANDIDATES
        ↓
   VALIDATOR
        ↓
ADMISSIBLE PLANS
        ↓
 DECISION / OVERRIDE
        ↓
  RESULTING STATE
        ↓
   EVENT HISTORY
        ↺
```

MultiFlow does not merely produce a static schedule.  
It **maintains a feasible operational state while reality changes**.

The key architectural rule:

> **MultiFlow owns the problem definition and correctness. Solvers only propose solutions.**

Infeasibility is first-class: the engine can return `NO_COMPLETE_SOLUTION` with blocking constraints and remaining capacity — it does not invent a schedule.

A future learned component may rank admissible candidates. It must never establish what is admissible.

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
PYTHONPATH=src python -m multiflow.demo.corporate
PYTHONPATH=src python -m multiflow.demo.live_recalculation
PYTHONPATH=src python -m multiflow.cli solve examples/simple.json
```

## Live recalculation

```python
from multiflow import SchedulingProblem, LiveEngine, EventType, SchedulingEvent

problem = SchedulingProblem.from_json("examples/corporate.json")
engine = LiveEngine(initial_problem=problem)
result = engine.recalculate()
```

Events are append-only. Snapshots capture reproducible solver input.  
Human overrides never erase the original solver decision.

## Solver fabric

| Backend | Install | Status |
|---------|---------|--------|
| Classical | core | always available |
| CP-SAT | `pip install "multiflow[cp-sat]"` | optional OR-Tools |
| MILP | `pip install "multiflow[milp]"` | optional PuLP |
| Quantum | companion | interface → `UNAVAILABLE` |

## Shared Evidence Contract

Decision and outcome evidence (`multiflow.evidence`) records proposed vs admitted
candidates, constraint versions, overrides, and optional upstream evidence refs.
See `docs/SHARED_EVIDENCE_CONTRACT.md`.

## What MultiFlow is

- Domain-neutral resource & task model
- First-class hard and soft constraints
- Independent validator (solver cannot define correctness)
- Multi-schedule support with shared-resource arbitration
- Explanation chains on every rejection
- Pluggable solver fabric
- Live event stream, snapshots, and recalculation
- Decision / override / outcome recording with evidence lineage
- Deterministic replay for audit

## License

MIT
