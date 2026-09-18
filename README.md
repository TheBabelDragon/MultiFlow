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

```
ScheduleFeatures
      ↓
CandidateScorer
      ↓
candidate ranking
      ↓
existing Validator
```

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

## Live recalculation

```python
from multiflow import SchedulingProblem, LiveEngine, EventType, SchedulingEvent

problem = SchedulingProblem.from_json("examples/corporate.json")
engine = LiveEngine(initial_problem=problem)

# Operational change
engine.apply_event(SchedulingEvent(
    event_type=EventType.RESOURCE_UNAVAILABLE,
    entity_ids=["forklift-17"],
    attributes={"resource_id": "forklift-17"},
    source="ops",
    reason="maintenance",
))

snap = engine.current_snapshot()
for cand, score in engine.rank_candidates(snap):
    print(cand.id, score, cand.score.admissible)
```

Events are append-only. Snapshots capture reproducible solver input.  
Rejected candidates retain their explanation chains (useful later as negative examples).  
Human overrides never erase the original solver decision.

Deterministic replay:

```python
from multiflow import LiveEngine

replayed = LiveEngine.replay(initial_problem, event_stream)
```

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
- **Live event stream, snapshots, and recalculation**
- **Candidate scoring boundary (deterministic now, learned later)**
- **Decision / override / outcome recording**
- **Deterministic replay for audit, regression, and future datasets**

## License

MIT
