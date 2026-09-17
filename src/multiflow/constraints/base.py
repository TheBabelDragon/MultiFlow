"""Constraint architecture.

Constraint -> evaluate(context) -> ConstraintResult
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from multiflow.domain.models import (
    Assignment,
    ConstraintResult,
    Resource,
    SchedulingProblem,
    Severity,
    Task,
    TimeWindow,
)


class EvaluationContext:
    """Everything a constraint needs to decide satisfaction."""

    def __init__(
        self,
        problem: SchedulingProblem,
        assignments: list[Assignment],
        focus_assignment: Optional[Assignment] = None,
    ):
        self.problem = problem
        self.assignments = assignments
        self.focus_assignment = focus_assignment
        self._resource_index = {r.id: r for r in problem.resources}
        self._task_index = {t.id: t for t in problem.tasks}

    def resource(self, rid: str) -> Optional[Resource]:
        return self._resource_index.get(rid)

    def task(self, tid: str) -> Optional[Task]:
        return self._task_index.get(tid)

    def assignments_for_resource(self, rid: str) -> list[Assignment]:
        return [a for a in self.assignments if rid in a.resource_ids]

    def assignments_for_task(self, tid: str) -> list[Assignment]:
        return [a for a in self.assignments if a.task_id == tid]


class Constraint(ABC):
    """First-class constraint object. Hard or soft."""

    def __init__(
        self,
        id: str,
        severity: Severity = Severity.HARD,
        name: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ):
        self.id = id
        self.severity = severity
        self.name = name or self.__class__.__name__
        self.attributes = attributes or {}

    @property
    def constraint_type(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        ...

    def _result(
        self,
        satisfied: bool,
        explanation: str = "",
        affected_resources: Optional[list[str]] = None,
        affected_tasks: Optional[list[str]] = None,
        time_range: Optional[TimeWindow] = None,
        penalty: float = 0.0,
        details: Optional[dict[str, Any]] = None,
    ) -> ConstraintResult:
        return ConstraintResult(
            satisfied=satisfied,
            severity=self.severity,
            constraint_id=self.id,
            constraint_type=self.constraint_type,
            affected_resources=affected_resources or [],
            affected_tasks=affected_tasks or [],
            time_range=time_range,
            penalty=0.0 if satisfied else (penalty if self.severity == Severity.SOFT else 0.0),
            explanation=explanation,
            details=details or {},
        )
