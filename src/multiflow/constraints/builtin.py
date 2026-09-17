"""Built-in hard and soft constraints."""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from multiflow.constraints.base import Constraint, EvaluationContext
from multiflow.domain.models import ConstraintResult, Severity, TimeWindow


class NoOverlapConstraint(Constraint):
    """HARD: a resource cannot be assigned to two overlapping windows."""

    def __init__(self, id: str = "no-overlap", resource_ids: Optional[list[str]] = None):
        super().__init__(id=id, severity=Severity.HARD, name="No Overlap")
        self.resource_ids = resource_ids

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        by_resource: dict[str, list] = {}
        for a in ctx.assignments:
            for rid in a.resource_ids:
                if self.resource_ids is not None and rid not in self.resource_ids:
                    continue
                by_resource.setdefault(rid, []).append(a)
        for rid, asns in by_resource.items():
            for i, a1 in enumerate(asns):
                for a2 in asns[i + 1 :]:
                    if a1.window.overlaps(a2.window):
                        overlap = a1.window.overlap_duration(a2.window)
                        results.append(
                            self._result(
                                satisfied=False,
                                explanation=(
                                    f"Resource {rid} double-booked: "
                                    f"assignment {a1.id} overlaps {a2.id} by {overlap}."
                                ),
                                affected_resources=[rid],
                                affected_tasks=[a1.task_id, a2.task_id],
                                time_range=TimeWindow(
                                    start=max(a1.window.start, a2.window.start),
                                    end=min(a1.window.end, a2.window.end),
                                ),
                                details={
                                    "assignment_a": a1.id,
                                    "assignment_b": a2.id,
                                    "overlap_seconds": overlap.total_seconds(),
                                },
                            )
                        )
        return results


class AvailabilityConstraint(Constraint):
    """HARD: assignment window must lie inside resource availability."""

    def __init__(self, id: str = "availability"):
        super().__init__(id=id, severity=Severity.HARD, name="Availability")

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        for a in ctx.assignments:
            for rid in a.resource_ids:
                res = ctx.resource(rid)
                if res is None:
                    results.append(
                        self._result(
                            satisfied=False,
                            explanation=f"Resource {rid} not found in problem.",
                            affected_resources=[rid],
                            affected_tasks=[a.task_id],
                            time_range=a.window,
                        )
                    )
                    continue
                if not res.is_available_during(a.window):
                    results.append(
                        self._result(
                            satisfied=False,
                            explanation=(
                                f"Resource {res.name} ({rid}) is unavailable for "
                                f"window {a.window.start.isoformat()}–{a.window.end.isoformat()}."
                            ),
                            affected_resources=[rid],
                            affected_tasks=[a.task_id],
                            time_range=a.window,
                        )
                    )
        return results


class CapabilityConstraint(Constraint):
    """HARD: assigned resources collectively cover every requirement."""

    def __init__(self, id: str = "capability"):
        super().__init__(id=id, severity=Severity.HARD, name="Capability")

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        for a in ctx.assignments:
            task = ctx.task(a.task_id)
            if task is None:
                continue
            assigned = [ctx.resource(rid) for rid in a.resource_ids]
            assigned = [r for r in assigned if r is not None]
            for req in task.requirements:
                if req.resource_ids:
                    if not any(r.id in req.resource_ids for r in assigned):
                        results.append(
                            self._result(
                                satisfied=False,
                                explanation=(
                                    f"Task {task.id} requires one of {req.resource_ids}; "
                                    f"assigned {[r.id for r in assigned]}."
                                ),
                                affected_resources=[r.id for r in assigned],
                                affected_tasks=[task.id],
                                time_range=a.window,
                            )
                        )
                    continue
                if req.capability:
                    covered = sum(1 for r in assigned if req.capability in r.capabilities)
                    if covered < req.quantity:
                        results.append(
                            self._result(
                                satisfied=False,
                                explanation=(
                                    f"Task {task.id} needs capability '{req.capability}' x{req.quantity}; "
                                    f"assigned resources cover {covered}."
                                ),
                                affected_resources=[r.id for r in assigned],
                                affected_tasks=[task.id],
                                time_range=a.window,
                            )
                        )
        return results


class CapacityConstraint(Constraint):
    """HARD: concurrent assignments on a resource cannot exceed capacity."""

    def __init__(self, id: str = "capacity"):
        super().__init__(id=id, severity=Severity.HARD, name="Capacity")

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        by_resource: dict[str, list] = {}
        for a in ctx.assignments:
            for rid in a.resource_ids:
                by_resource.setdefault(rid, []).append(a)
        for rid, asns in by_resource.items():
            res = ctx.resource(rid)
            if res is None:
                continue
            cap = max(1, res.capacity)
            for a1 in asns:
                concurrent = sum(1 for a2 in asns if a1.window.overlaps(a2.window))
                if concurrent > cap:
                    results.append(
                        self._result(
                            satisfied=False,
                            explanation=(
                                f"Resource {rid} capacity {cap} exceeded "
                                f"({concurrent} concurrent assignments)."
                            ),
                            affected_resources=[rid],
                            affected_tasks=[a1.task_id],
                            time_range=a1.window,
                        )
                    )
                    break
        return results


class TimeWindowConstraint(Constraint):
    """HARD: assignment must lie inside task allowed windows."""

    def __init__(self, id: str = "allowed-window"):
        super().__init__(id=id, severity=Severity.HARD, name="Allowed Window")

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        for a in ctx.assignments:
            task = ctx.task(a.task_id)
            if task is None or not task.allowed_windows:
                continue
            ok = any(
                w.start <= a.window.start and w.end >= a.window.end
                for w in task.allowed_windows
            )
            if not ok:
                results.append(
                    self._result(
                        satisfied=False,
                        explanation=(
                            f"Assignment for task {a.task_id} outside allowed windows."
                        ),
                        affected_tasks=[a.task_id],
                        time_range=a.window,
                    )
                )
        return results


class ProtectedWindowConstraint(Constraint):
    """HARD: enforce minimum separation between assignments on same resource."""

    def __init__(self, id: str = "protected-window", min_separation: Optional[timedelta] = None):
        super().__init__(id=id, severity=Severity.HARD, name="Protected Window")
        self.min_separation = min_separation or timedelta(minutes=15)

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        by_resource: dict[str, list] = {}
        for a in ctx.assignments:
            for rid in a.resource_ids:
                by_resource.setdefault(rid, []).append(a)
        for rid, asns in by_resource.items():
            ordered = sorted(asns, key=lambda a: a.window.start)
            for i in range(len(ordered) - 1):
                a1, a2 = ordered[i], ordered[i + 1]
                gap = a2.window.start - a1.window.end
                if gap < self.min_separation and not a1.window.overlaps(a2.window):
                    results.append(
                        self._result(
                            satisfied=False,
                            explanation=(
                                f"Resource {rid}: gap {gap} < min separation {self.min_separation}."
                            ),
                            affected_resources=[rid],
                            affected_tasks=[a1.task_id, a2.task_id],
                        )
                    )
        return results


class PreferredResourceConstraint(Constraint):
    """SOFT: prefer listed resources."""

    def __init__(self, id: str = "preferred-resource", preferred: Optional[list[str]] = None, penalty: float = 1.0):
        super().__init__(id=id, severity=Severity.SOFT, name="Preferred Resource")
        self.preferred = preferred or []
        self.penalty_value = penalty

    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        results: list[ConstraintResult] = []
        if not self.preferred:
            return results
        for a in ctx.assignments:
            if not any(rid in self.preferred for rid in a.resource_ids):
                results.append(
                    self._result(
                        satisfied=False,
                        explanation=f"Assignment {a.id} did not use preferred resources.",
                        affected_resources=a.resource_ids,
                        affected_tasks=[a.task_id],
                        penalty=self.penalty_value,
                    )
                )
        return results
