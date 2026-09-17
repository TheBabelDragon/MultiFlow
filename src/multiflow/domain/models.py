"""Core domain model for MultiFlow.

All entities are domain-neutral.  No assumptions about employees, shows,
or any particular industry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class TimeWindow(BaseModel):
    schema_version: str = "multiflow.timewindow.v1"
    id: str = Field(default_factory=lambda: _new_id("tw"))
    start: datetime
    end: datetime
    label: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _check_order(self) -> "TimeWindow":
        if self.end <= self.start:
            raise ValueError("TimeWindow.end must be strictly after start")
        return self

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: "TimeWindow") -> bool:
        return self.start < other.end and other.start < self.end

    def overlap_duration(self, other: "TimeWindow") -> timedelta:
        if not self.overlaps(other):
            return timedelta(0)
        return min(self.end, other.end) - max(self.start, other.start)

    def contains(self, instant: datetime) -> bool:
        return self.start <= instant < self.end


class ResourceType(str, Enum):
    WORKER = "worker"
    TEAM = "team"
    ROOM = "room"
    VEHICLE = "vehicle"
    MACHINE = "machine"
    EQUIPMENT = "equipment"
    FACILITY = "facility"
    DEPARTMENT = "department"
    COMPUTER = "computer"
    GPU = "gpu"
    PRODUCTION_LINE = "production_line"
    APPOINTMENT_SLOT = "appointment_slot"
    EXTERNAL_SERVICE = "external_service"
    OTHER = "other"


class Resource(BaseModel):
    schema_version: str = "multiflow.resource.v1"
    id: str = Field(default_factory=lambda: _new_id("res"))
    type: ResourceType = ResourceType.OTHER
    name: str = ""
    capabilities: list[str] = Field(default_factory=list)
    availability: list[TimeWindow] = Field(default_factory=list)
    capacity: int = 1
    attributes: dict[str, Any] = Field(default_factory=dict)

    def is_available_during(self, window: TimeWindow) -> bool:
        if not self.availability:
            return True
        return any(
            a.start <= window.start and a.end >= window.end for a in self.availability
        )


class Requirement(BaseModel):
    schema_version: str = "multiflow.requirement.v1"
    capability: Optional[str] = None
    resource_type: Optional[ResourceType] = None
    resource_ids: list[str] = Field(default_factory=list)
    quantity: int = 1
    attributes: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    schema_version: str = "multiflow.task.v1"
    id: str = Field(default_factory=lambda: _new_id("task"))
    name: str = ""
    requirements: list[Requirement] = Field(default_factory=list)
    duration: timedelta = Field(default_factory=lambda: timedelta(hours=1))
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    schedule_id: Optional[str] = None
    priority: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)


class Severity(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class Assignment(BaseModel):
    schema_version: str = "multiflow.assignment.v1"
    id: str = Field(default_factory=lambda: _new_id("asg"))
    task_id: str
    resource_ids: list[str] = Field(default_factory=list)
    window: TimeWindow
    schedule_id: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class Schedule(BaseModel):
    schema_version: str = "multiflow.schedule.v1"
    id: str = Field(default_factory=lambda: _new_id("sch"))
    name: str = ""
    domain: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ObjectiveDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


class Objective(BaseModel):
    schema_version: str = "multiflow.objective.v1"
    id: str = Field(default_factory=lambda: _new_id("obj"))
    name: str = ""
    direction: ObjectiveDirection = ObjectiveDirection.MINIMIZE
    weight: float = 1.0
    attributes: dict[str, Any] = Field(default_factory=dict)


class SchedulingProblem(BaseModel):
    schema_version: str = "multiflow.problem.v1"
    id: str = Field(default_factory=lambda: _new_id("prob"))
    resources: list[Resource] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    constraints: list[Any] = Field(default_factory=list)
    objectives: list[Objective] = Field(default_factory=list)
    schedules: list[Schedule] = Field(default_factory=list)
    existing_assignments: list[Assignment] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

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
    def from_json(cls, path_or_data):
        from multiflow.serialization.io import load_problem
        if isinstance(path_or_data, dict):
            import json as _json
            import tempfile, os
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                _json.dump(path_or_data, f)
                tmp = f.name
            try:
                return load_problem(tmp)
            finally:
                os.unlink(tmp)
        return load_problem(path_or_data)

    def to_json(self, path=None):
        from multiflow.serialization.io import dump_problem
        if path is not None:
            dump_problem(self, path)
            return path
        import json as _json
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            dump_problem(self, f.name)
            tmp = f.name
        try:
            with open(tmp) as fh:
                return _json.load(fh)
        finally:
            os.unlink(tmp)


class SolutionScore(BaseModel):
    schema_version: str = "multiflow.score.v1"
    total: float = 0.0
    hard_violations: int = 0
    soft_penalty: float = 0.0
    objective_breakdown: dict[str, float] = Field(default_factory=dict)
    admissible: bool = True


class CandidateSolution(BaseModel):
    schema_version: str = "multiflow.candidate.v1"
    id: str = Field(default_factory=lambda: _new_id("cand"))
    problem_id: str
    assignments: list[Assignment] = Field(default_factory=list)
    score: SolutionScore = Field(default_factory=SolutionScore)
    solver_id: Optional[str] = None
    solver_version: Optional[str] = None
    configuration: dict[str, Any] = Field(default_factory=dict)
    timestamp: Optional[datetime] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ConstraintResult(BaseModel):
    schema_version: str = "multiflow.constraint_result.v1"
    satisfied: bool
    severity: Severity
    constraint_id: str
    constraint_type: str
    affected_resources: list[str] = Field(default_factory=list)
    affected_tasks: list[str] = Field(default_factory=list)
    time_range: Optional[TimeWindow] = None
    penalty: float = 0.0
    explanation: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    schema_version: str = "multiflow.validation.v1"
    candidate_id: str
    admissible: bool
    hard_violations: list[ConstraintResult] = Field(default_factory=list)
    soft_results: list[ConstraintResult] = Field(default_factory=list)
    score: SolutionScore = Field(default_factory=SolutionScore)
    explanation_chain: list[str] = Field(default_factory=list)


class ScheduleConflict(BaseModel):
    schema_version: str = "multiflow.conflict.v1"
    id: str = Field(default_factory=lambda: _new_id("cnf"))
    schedule_a: Optional[str] = None
    schedule_b: Optional[str] = None
    resource_id: str
    time_range: TimeWindow
    conflicting_assignments: list[str] = Field(default_factory=list)
    constraint_id: Optional[str] = None
    severity: Severity = Severity.HARD
    explanation: str = ""
    possible_resolutions: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
