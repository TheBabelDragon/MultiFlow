"""Multi-schedule conflict detection and simple arbitration."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from multiflow.constraints.builtin import NoOverlapConstraint
from multiflow.constraints.base import EvaluationContext
from multiflow.domain.models import (
    Assignment,
    ScheduleConflict,
    SchedulingProblem,
    Severity,
)
from multiflow.solver.classical import ClassicalSolver
from multiflow.validation.validator import Validator


class ConflictDetector:
    """Detect intra- and cross-schedule conflicts on shared resources."""

    def detect(
        self,
        problem: SchedulingProblem,
        assignments: list[Assignment],
    ) -> list[ScheduleConflict]:
        conflicts: list[ScheduleConflict] = []
        ctx = EvaluationContext(problem, assignments)
        for result in NoOverlapConstraint().evaluate(ctx):
            if result.satisfied:
                continue
            details = result.details
            a_id = details.get("assignment_a")
            b_id = details.get("assignment_b")
            asn_a = next((x for x in assignments if x.id == a_id), None)
            asn_b = next((x for x in assignments if x.id == b_id), None)
            tr = result.time_range
            if tr is None and asn_a is not None:
                tr = asn_a.window
            elif tr is None and assignments:
                tr = assignments[0].window
            conflicts.append(
                ScheduleConflict(
                    schedule_a=asn_a.schedule_id if asn_a else None,
                    schedule_b=asn_b.schedule_id if asn_b else None,
                    resource_id=result.affected_resources[0] if result.affected_resources else "",
                    time_range=tr,
                    conflicting_assignments=[a_id, b_id] if a_id and b_id else list(result.affected_tasks),
                    constraint_id=result.constraint_id,
                    severity=Severity.HARD,
                    explanation=result.explanation,
                    possible_resolutions=self._suggest_resolutions(asn_a, asn_b),
                )
            )
        return conflicts

    def _suggest_resolutions(
        self,
        a: Optional[Assignment],
        b: Optional[Assignment],
    ) -> list[str]:
        if not a or not b:
            return ["Reassign one of the tasks to a different resource."]
        suggestions = []
        shift = a.window.end - b.window.start + timedelta(minutes=5)
        if shift > timedelta(0):
            suggestions.append(f"Delay assignment {b.id} by {shift}.")
        shift2 = b.window.end - a.window.start + timedelta(minutes=5)
        if shift2 > timedelta(0):
            suggestions.append(f"Delay assignment {a.id} by {shift2}.")
        suggestions.append("Move one of the tasks to a different resource.")
        return suggestions


class Arbitrator:
    """Detect → explain → generate alternatives → score → validate."""

    def __init__(self):
        self.detector = ConflictDetector()
        self.solver = ClassicalSolver(max_candidates=5)
        self.validator = Validator()

    def arbitrate(
        self,
        problem: SchedulingProblem,
        current_assignments: list[Assignment],
    ) -> dict:
        conflicts = self.detector.detect(problem, current_assignments)
        if not conflicts:
            return {"conflicts": [], "candidates": [], "message": "No conflicts detected."}

        candidates = self.solver.solve(problem)
        validated = []
        for c in candidates:
            vr = self.validator.validate(problem, c)
            validated.append(
                {
                    "candidate_id": c.id,
                    "admissible": vr.admissible,
                    "hard_violations": vr.score.hard_violations,
                    "soft_penalty": vr.score.soft_penalty,
                    "explanation_chain": vr.explanation_chain,
                }
            )
        return {
            "conflicts": [c.model_dump(mode="json") for c in conflicts],
            "candidates": validated,
            "message": f"{len(conflicts)} conflict(s); {sum(1 for v in validated if v['admissible'])} admissible alternative(s).",
        }
