# MultiFlow

**MultiFlow is a general-purpose scheduling and constraint-arbitration engine for systems with shared resources.**

Showflow proves scheduling in one domain.  
MultiFlow generalizes the scheduling substrate.  
A future quantum companion can explore alternate optimization backends.

MultiFlow schedules **interacting systems**, not merely people.

```
DOMAIN
  ↓
NORMALIZED SCHEDULING PROBLEM
  ↓
SOLVER FABRIC
  ↓
VALIDATED SCHEDULE
```

The key architectural rule:

> **MultiFlow owns the problem definition and correctness. Solvers only propose solutions.**

A candidate is never correct merely because an optimizer likes its score.  
Every candidate is independently validated against hard constraints.

---

## What MultiFlow is

- Domain-neutral resource & task model
- First-class hard and soft constraints
- Independent validator (solver cannot define correctness)
- Multi-schedule support with shared-resource arbitration
- Explanation engine (causal chains for rejections)
- Pluggable solver fabric (classical first; MILP / CP-SAT / quantum later)
- Deterministic classical solver for the MVP
- JSON schema-versioned serialization

## What MultiFlow is not (yet)

- LLM-first scheduling
- Autonomous agents
- Payroll / HR / CRM / ERP
- Quantum hardware integration
- Enterprise SSO or billing

---

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
PYTHONPATH=src python -m multiflow.demo.corporate
```

Web UI:

```bash
PYTHONPATH=src uvicorn multiflow.api.app:app --reload
# open http://localhost:8000
```

---

## Showflow relationship

Showflow remains a focused domain application.  
MultiFlow does **not** rewrite or absorb Showflow.

| Showflow          | MultiFlow              |
|-------------------|------------------------|
| Worker            | Resource               |
| Show / Showtime   | Task                   |
| SetTime (A/B/C)   | TimeWindow + derived   |
| Assignment        | Assignment             |
| Hard no-overlap   | Hard Constraint        |
| Soft scoring      | Objective              |

---

## License

MIT
