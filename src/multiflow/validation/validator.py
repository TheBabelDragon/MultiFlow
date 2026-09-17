"""Independent validator.

CandidateSolution
       ↓
Validator
       ↓
ValidationResult

The validator re-checks availability, capacity, overlap, requirements,
hard constraints, time windows, and resource compatibility.
This prevents any solver from defining correctness by accident.
"""

from __future__ import annotations

from typing import Optional

from multiflow.constraints.base import Constraint, EvaluationContext
from multiflow.constraints.builtin import (
    AvailabilityConstraint,
    CapabilityConstraint,
    CapacityConstraint,
    NoOverlapConstraint,
    TimeWindowConstraint,
)
from multiflow.domain.models import (
    CandidateSolution,
    ConstraintResult,
    SchedulingProblem,
    Severity,
    SolutionScore,
    ValidationResult,
)


class Validator:
    """Independent admissibility checker."""

    def __init__(self, extra_constraints: Optional[list[Constraint]] = None):
        self.builtin = [
            NoOverlapConstraint(),
            AvailabilityConstraint(),
            CapabilityConstraint(),
            CapacityConstraint(),
            TimeWindowConstraint(),
        ]
        self.extra = extra_constraints or []

    def validate(
        self,
        problem: SchedulingProblem,
        candidate: CandidateSolution,
    ) -> ValidationResult:
        all_constraints: list[Constraint] = list(self.builtin)
        for c in problem.constraints:
            if isinstance(c, Constraint):
                all_constraints.append(c)
        all_constraints.extend(self.extra)

        ctx = EvaluationContext(problem, candidate.assignments)
        hard: list[ConstraintResult] = []
        soft: list[ConstraintResult] = []
        chain: list[str] = []

        for constraint in all_constraints:
            for result in constraint.evaluate(ctx):
                if result.severity == Severity.HARD:
                    if not result.satisfied:
                        hard.append(result)
                        chain.append(
                            f"HARD VIOLATION [{result.constraint_type}] "
                            f"{result.explanation}"
                        )
                else:
                    soft.append(result)
                    if not result.satisfied:
                        chain.append(
                            f"SOFT [{result.constraint_type}] "
                            f"penalty={result.penalty}: {result.explanation}"
                        )

        soft_penalty = sum(r.penalty for r in soft if not r.satisfied)
        admissible = len(hard) == 0
        score = SolutionScore(
            total=soft_penalty if admissible else float("inf"),
            hard_violations=len(hard),
            soft_penalty=soft_penalty,
            admissible=admissible,
        )
        return ValidationResult(
            candidate_id=candidate.id,
            admissible=admissible,
            hard_violations=hard,
            soft_results=soft,
            score=score,
            explanation_chain=chain,
        )
