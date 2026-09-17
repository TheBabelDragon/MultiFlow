# Architecture

```
DOMAIN
  ↓
NORMALIZED SCHEDULING PROBLEM
  ↓
SOLVER FABRIC
  ↓
VALIDATED SCHEDULE
```

## Ownership rule

MultiFlow owns the problem definition and correctness.  
Solvers only propose candidates.  
The independent `Validator` decides admissibility.

## Layers

1. **Domain** – Resource, Task, TimeWindow, Constraint, Assignment, Schedule, …
2. **Constraints** – first-class hard/soft objects with rich `ConstraintResult`
3. **Solver fabric** – `Solver.solve(problem) → list[CandidateSolution]`
4. **Validation** – re-checks every candidate
5. **Arbitration** – multi-schedule conflict detection + alternative generation
6. **Explanation** – causal chains on every rejection

## Future reality loop

```
PLAN → EXECUTE → OBSERVE → COMPARE → DEVIATION → RE-SOLVE → NEW PLAN
```
