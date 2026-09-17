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

---

## What MultiFlow is

- Domain-neutral resource & task model
- First-class hard and soft constraints
- Independent validator (solver cannot define correctness)
- Multi-schedule support with shared-resource arbitration
- Explanation chains on every rejection
- Pluggable solver fabric (classical first)
- Deterministic classical solver
- Schema-versioned JSON problem format + CLI

## What MultiFlow is not (yet)

- LLM-first scheduling · autonomous agents · payroll/HR/CRM/ERP
- Quantum hardware integration · enterprise SSO · billing

---

## Showflow relationship

Showflow remains a focused domain application. MultiFlow does **not** rewrite or absorb it.

| Showflow | MultiFlow |
|----------|-----------|
| Worker | Resource |
| Show / Showtime | Task |
| SetTime (A/B/C) | TimeWindow |
| Hard no-overlap | Hard Constraint |
| Soft scoring | Objective |

---

## License

MIT
