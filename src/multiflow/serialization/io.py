"""Versioned JSON load/dump for SchedulingProblem and solution reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from multiflow.constraints.builtin import (
    AvailabilityConstraint,
    CapabilityConstraint,
    CapacityConstraint,
    NoOverlapConstraint,
    PreferredResourceConstraint,
    ProtectedWindowConstraint,
    TimeWindowConstraint,
)
from multiflow.domain.models import (
    Objective,
    Resource,
    Schedule,
    SchedulingProblem,
    Task,
)

_CONSTRAINT_MAP = {
    "NoOverlapConstraint": NoOverlapConstraint,
    "AvailabilityConstraint": AvailabilityConstraint,
    "CapabilityConstraint": CapabilityConstraint,
    "CapacityConstraint": CapacityConstraint,
    "ProtectedWindowConstraint": ProtectedWindowConstraint,
    "PreferredResourceConstraint": PreferredResourceConstraint,
    "TimeWindowConstraint": TimeWindowConstraint,
}


def _hydrate_constraints(raw: list[Any]) -> list:
    out = []
    for item in raw:
        if isinstance(item, dict):
            ctype = item.get("type") or item.get("constraint_type") or item.get("name")
            cls = _CONSTRAINT_MAP.get(ctype)
            if cls is None:
                continue
            kwargs = {
                k: v
                for k, v in item.items()
                if k not in ("type", "constraint_type", "name", "schema_version")
            }
            if "min_separation" in kwargs and isinstance(kwargs["min_separation"], (int, float)):
                from datetime import timedelta

                kwargs["min_separation"] = timedelta(seconds=kwargs["min_separation"])
            try:
                out.append(cls(**kwargs) if kwargs else cls())
            except TypeError:
                out.append(cls())
        else:
            out.append(item)
    return out


def load_problem(path: Union[str, Path]) -> SchedulingProblem:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError("Problem JSON must be an object")
    schema = data.get("schema_version") or data.get("schema")
    if schema and not str(schema).startswith("multiflow.problem"):
        raise ValueError(f"Unexpected schema: {schema}")

    # Normalize duration_seconds -> duration ISO if present
    for t in data.get("tasks", []):
        if "duration_seconds" in t and "duration" not in t:
            secs = t.pop("duration_seconds")
            t["duration"] = f"PT{int(secs)}S"

    resources = [Resource.model_validate(r) for r in data.get("resources", [])]
    tasks = [Task.model_validate(t) for t in data.get("tasks", [])]
    schedules = [Schedule.model_validate(s) for s in data.get("schedules", [])]
    objectives = [Objective.model_validate(o) for o in data.get("objectives", [])]
    constraints = _hydrate_constraints(data.get("constraints", []))

    return SchedulingProblem(
        id=data.get("id", "prob-loaded"),
        resources=resources,
        tasks=tasks,
        schedules=schedules,
        objectives=objectives,
        constraints=constraints,
        attributes=data.get("attributes", {}),
    )


def dump_problem(problem: SchedulingProblem, path: Union[str, Path]) -> None:
    serialized_constraints = []
    for c in problem.constraints:
        if hasattr(c, "constraint_type"):
            entry = {"type": c.constraint_type, "id": getattr(c, "id", None)}
            if hasattr(c, "min_separation"):
                entry["min_separation"] = c.min_separation.total_seconds()
            serialized_constraints.append(entry)
    data = problem.model_dump(mode="json", exclude={"constraints"})
    data["constraints"] = serialized_constraints
    data["schema_version"] = data.get("schema_version") or "multiflow.problem.v1"
    Path(path).write_text(json.dumps(data, indent=2) + "\n")


def dump_solution_report(report: dict, path: Union[str, Path]) -> None:
    Path(path).write_text(json.dumps(report, indent=2) + "\n")
