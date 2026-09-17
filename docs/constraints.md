# Constraints

Constraints are first-class objects.

```
Constraint.evaluate(context) → list[ConstraintResult]
```

A `ConstraintResult` always carries satisfied, severity, constraintId, affected resources & tasks, time range, penalty, explanation.

## Built-in hard constraints

- NoOverlap
- Availability
- Capability
- Capacity
- Allowed TimeWindow
- ProtectedWindow

Hard violations make a candidate inadmissible. Soft penalties only rank admissible candidates.
