"""Core domain model for MultiFlow.

All entities are domain-neutral.  No assumptions about employees,
vehicles, or any other concrete domain.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class TimeWindow(BaseModel):
    schema_version: str = "multiflow.timewindow.v1"
    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _check_order(self) -> "TimeWindow":
        if self.end <= self.start:
            raise ValueError("TimeWindow end must be after start")
        return self

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: "TimeWindow") -> bool:
        return self.start <= other.start and self.end >= other.end

    def duration(self) -> timedelta:
        return self.end - self.start


class ResourceType(str, Enum):
    WORKER = "worker"
    VEHICLE = "vehicle"
    EQUIPMENT = "equipment"
    LOCATION = "location"
    GENERIC = "generic"


class Resource(BaseModel):
    schema_version: str = "multiflow.resource.v1"
    id: str
    type: ResourceType = ResourceType.GENERIC
    name: str = ""
    capabilities: list[str] = Field(default_factory=list)
    availability: list[TimeWindow] = Field(default_factory=list)
    capacity: int = 1
    attributes: dict[str, Any] = Field(default_factory=dict)

    def is_available_during(self, window: TimeWindow) -> bool:
        # Empty availability means the resource is not available in any window.
        if not self.availability:
            return False
        return any(
            a.start <= window.start and a.end >= window.end for a in self.availability
        )


class Requirement(BaseModel):
    schema_version: str = "multiflow.requirement.v1"
    capability: str = ""
    quantity: int = 1
    resource_type: Optional[ResourceType] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    schema_version: str = "multiflow.task.v1"
    id: str
    name: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    duration: Optional[timedelta] = None
    duration_seconds: Optional[int] = None
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    priority: int = 0
    dependencies: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _normalize_duration(self) -> "Task":
        if self.duration is None and self.duration_seconds is not None:
            object.__setattr__(self, "duration", timedelta(seconds=self.duration_seconds))
        elif self.duration is not None and self.duration_seconds is None:
            object.__setattr__(self, "duration_seconds", int(self.duration.total_seconds()))
        return self


class Severity(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class Assignment(BaseModel):
    schema_version: str = "multiflow.assignment.v1"
    task_id: str
    resource_ids: list[str] = Field(default_factory=list)
    window: Optional[TimeWindow] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class Schedule(BaseModel):
    schema_version: str = "multiflow.schedule.v1"
    id: str = ""
    assignments: list[Assignment] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ObjectiveDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class Objective(BaseModel):
    schema_version: str = "multiflow.objective.v1"
    name: str
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE
    weight: float = 1.0
    attributes: dict[str, Any] = Field(default_factory=dict)


class SchedulingProblem(BaseModel):
    schema_version: str = "multiflow.problem.v1"
    id: str = ""
    resources: list[Resource] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    existing_assignments: list[Assignment] = Field(default_factory=list)
    schedules: list[Schedule] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    horizon: Optional[TimeWindow] = None

    def resource_by_id(self, rid: str) -> Optional[Resource]:
        for r in self.resources:
            if r.id == rid:
                return r
        return None

    def task_by_id(self, tid: str) -> Optional[Task]:
        for t in self.tasks:
            if t.id == tid:
                return t
        return None

    @classmethod
    def from_json(cls, path: str) -> "SchedulingProblem":
        from multiflow.serialization.io import load_problem

        return load_problem(path)


class SolutionScore(BaseModel):
    schema_version: str = "multiflow.score.v1"
    total: float = 0.0
    components: dict[str, float] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class CandidateSolution(BaseModel):
    schema_version: str = "multiflow.candidate.v1"
    id: str = ""
    assignments: list[Assignment] = Field(default_factory=list)
    score: Optional[SolutionScore] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ConstraintResult(BaseModel):
    schema_version: str = "multiflow.constraint_result.v1"
    constraint_id: str = ""
    satisfied: bool = True
    severity: Severity = Severity.HARD
    explanation: str = ""
    attributes: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    schema_version: str = "multiflow.validation.v1"
    admissible: bool = True
    hard_violations: list[ConstraintResult] = Field(default_factory=list)
    soft_violations: list[ConstraintResult] = Field(default_factory=list)
    explanation_chain: list[str] = Field(default_factory=list)
    score: SolutionScore = Field(default_factory=SolutionScore)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return self.admissible


class ScheduleConflict(BaseModel):
    schema_version: str = "multiflow.conflict.v1"
    id: str = ""
    description: str = ""
    involved_task_ids: list[str] = Field(default_factory=list)
    involved_resource_ids: list[str] = Field(default_factory=list)
    severity: Severity = Severity.HARD
    attributes: dict[str, Any] = Field(default_factory=dict)
