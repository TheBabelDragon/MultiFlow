"""Reproducible schedule snapshots for live recalculation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from multiflow.domain.models import SchedulingProblem


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ScheduleSnapshot(BaseModel):
    """Capture of reproducible solver input at a point in the event stream.

    Stores a deep copy of the normalized SchedulingProblem rather than a
    reference to mutable live state.
    """

    schema_version: str = "multiflow.snapshot.v1"
    id: str = Field(default_factory=lambda: _new_id("snap"))
    problem_id: str
    problem_version: str = "1"
    event_sequence_position: int = 0
    timestamp: datetime = Field(default_factory=_utc_now)
    problem: SchedulingProblem
    event_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_problem(
        cls,
        problem: SchedulingProblem,
        event_sequence_position: int = 0,
        event_ids: Optional[list[str]] = None,
        attributes: Optional[dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "ScheduleSnapshot":
        """Build a snapshot with a deep-copied problem for reproducibility."""
        problem_copy = SchedulingProblem.model_validate(problem.model_dump())
        kwargs: dict[str, Any] = {
            "problem_id": problem.id,
            "problem_version": problem.attributes.get("version", "1")
            if isinstance(problem.attributes, dict)
            else "1",
            "event_sequence_position": event_sequence_position,
            "problem": problem_copy,
            "event_ids": list(event_ids or []),
            "attributes": dict(attributes or {}),
        }
        if snapshot_id is not None:
            kwargs["id"] = snapshot_id
        if timestamp is not None:
            kwargs["timestamp"] = timestamp
        return cls(**kwargs)

    def semantic_fingerprint(self) -> dict[str, Any]:
        """Stable comparison key ignoring ephemeral IDs/timestamps."""
        p = self.problem
        return {
            "problem_id": p.id,
            "event_sequence_position": self.event_sequence_position,
            "resource_ids": sorted(r.id for r in p.resources),
            "resource_availability": {
                r.id: [
                    (w.start.isoformat(), w.end.isoformat()) for w in r.availability
                ]
                for r in sorted(p.resources, key=lambda x: x.id)
            },
            "resource_capacity": {r.id: r.capacity for r in p.resources},
            "task_ids": sorted(t.id for t in p.tasks),
            "task_priorities": {t.id: t.priority for t in p.tasks},
            "existing_assignment_task_ids": sorted(
                a.task_id for a in p.existing_assignments
            ),
        }
