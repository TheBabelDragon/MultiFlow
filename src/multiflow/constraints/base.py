"""Constraint base classes and evaluation context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from multiflow.domain.models import (
    Assignment,
    ConstraintResult,
    SchedulingProblem,
    Severity,
)


class EvaluationContext:
    """Shared context for constraint evaluation."""

    def __init__(self, problem: SchedulingProblem, assignments: list[Assignment]):
        self.problem = problem
        self.assignments = list(assignments)
        self._by_resource: dict[str, list[Assignment]] | None = None
        self._by_task: dict[str, list[Assignment]] | None = None

    def assignments_for_resource(self, resource_id: str) -> list[Assignment]:
        if self._by_resource is None:
            self._by_resource = {}
            for a in self.assignments:
                for rid in a.resource_ids:
                    self._by_resource.setdefault(rid, []).append(a)
        return self._by_resource.get(resource_id, [])

    def assignments_for_task(self, task_id: str) -> list[Assignment]:
        if self._by_task is None:
            self._by_task = {}
            for a in self.assignments:
                self._by_task.setdefault(a.task_id, []).append(a)
        return self._by_task.get(task_id, [])

    def resource(self, resource_id: str):
        return self.problem.resource_by_id(resource_id)

    def task(self, task_id: str):
        return self.problem.task_by_id(task_id)


class Constraint(ABC):
    """Hard or soft constraint. Never returns a bare bool."""

    id: str = "constraint"
    severity: Severity = Severity.HARD

    @abstractmethod
    def evaluate(self, ctx: EvaluationContext) -> list[ConstraintResult]:
        """Return zero or more ConstraintResult objects."""
        ...
