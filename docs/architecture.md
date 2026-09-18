# Architecture

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

## Ownership rule

MultiFlow owns the problem definition and correctness.  
Solvers only propose candidates.  
The independent `Validator` decides admissibility.  
A `CandidateScorer` may rank admissible options; it never establishes correctness.

## Layers

1. **Domain** – Resource, Task, TimeWindow, Constraint, Assignment, Schedule, …
2. **Constraints** – first-class hard/soft objects with rich `ConstraintResult`
3. **Solver fabric** – `Solver.solve(problem) → list[CandidateSolution]`
4. **Validation** – re-checks every candidate
5. **Arbitration** – multi-schedule conflict detection + alternative generation
6. **Explanation** – causal chains on every rejection
7. **Live events** – append-only `SchedulingEvent` stream
8. **Snapshots** – reproducible normalized state before each solve
9. **Features / scoring** – `ScheduleFeatures` → `CandidateScorer` (preference only)
10. **Decisions & outcomes** – solver decision, human override, actual outcome kept distinct
11. **Replay** – initial state + ordered events → equivalent normalized state

## Future learned ranking

```
ScheduleFeatures
      ↓
CandidateScorer   (may become NeuralCandidateScorer)
      ↓
candidate ranking
      ↓
existing Validator
```

MultiFlow learns which *admissible* option tends to work well.  
It does **not** learn what constitutes an admissible schedule.

## Reality loop

```
PLAN → EXECUTE → OBSERVE → COMPARE → DEVIATION → RE-SOLVE → NEW PLAN
```
