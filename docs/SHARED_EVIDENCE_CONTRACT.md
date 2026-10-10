# Shared Evidence Contract — MultiFlow (Phase 5)

**Status:** Implemented — decision and outcome evidence records.

## Ownership

| Layer | Owns |
|-------|------|
| CANtheon / CANgate | physical transport evidence |
| MetaField | field semantics + EvidenceLineage |
| TensorGate | numerical / computational lineage |
| **MultiFlow** | decision inputs, constraint versions, admitted vs proposed, outcomes |
| Aurora Mesh | distributed integrity (next) |

## DecisionEvidence fields

- `proposed_candidate_ids` — solver proposals (not yet admitted)
- `admitted_candidate_id` — validated + selected result
- `rejected_candidate_ids` + `rejection_reasons` — alternatives with explanations
- `constraint_versions` — constraint set identity at decision time
- `outcome_status` — ADMITTED / REJECTED / OVERRIDE / NO_SOLUTION / PROPOSED
- `outcome_id` — stable outcome identity
- `human_override` / `override_of_decision_id` — audit; never erases history
- `evidence_refs` — optional upstream links (plain dicts)
- `solver_id` / `solver_version`

## Rules

1. Solver proposals and admitted results are distinct fields.
2. ADMITTED requires `admitted_candidate_id`.
3. Overrides add a new record; they do not mutate the original.
4. Schema major mismatch fails closed.
5. Core does not import CANtheon, MetaField, or TensorGate.

## API

```python
from multiflow import (
    build_decision_evidence, OutcomeStatus, ConstraintVersion,
    attach_evidence_ref, decision_record_to_evidence,
)

ev = build_decision_evidence(
    snapshot_id="snap-1",
    proposed_candidate_ids=["c1", "c2"],
    admitted_candidate_id="c1",
    outcome_status=OutcomeStatus.ADMITTED,
    constraint_versions=[ConstraintVersion(constraint_id="no_overlap", version="1.0")],
)
```

## Verification

```bash
PYTHONPATH=src pytest tests/test_evidence.py -q
```
