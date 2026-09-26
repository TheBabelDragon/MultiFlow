"""Immutable, append-only scheduling events for MultiFlow live operations."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterator, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventType(str, Enum):
    RESOURCE_UNAVAILABLE = "resource_unavailable"
    RESOURCE_AVAILABLE = "resource_available"
    RESOURCE_CAPACITY_CHANGED = "resource_capacity_changed"
    TASK_ADDED = "task_added"
    TASK_REMOVED = "task_removed"
    TASK_CHANGED = "task_changed"
    ASSIGNMENT_CHANGED = "assignment_changed"
    CONSTRAINT_CHANGED = "constraint_changed"
    SCHEDULE_CHANGED = "schedule_changed"
    HUMAN_OVERRIDE = "human_override"


class SchedulingEvent(BaseModel):
    """Immutable historical fact. Never rewrite to represent resulting state."""

    schema_version: str = "multiflow.event.v1"
    id: str = Field(default_factory=lambda: _new_id("evt"))
    event_type: EventType
    entity_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    source: str = "system"
    reason: str = ""
    timestamp: datetime = Field(default_factory=_utc_now)

    model_config = {"frozen": True}


class EventStore:
    """Append-only store of SchedulingEvent instances.

    Historical events are never mutated or removed. Export/import is
    deterministic given the same ordered event sequence.
    """

    def __init__(self, events: Optional[list[SchedulingEvent]] = None) -> None:
        self._events: list[SchedulingEvent] = list(events or [])

    def append(self, event: SchedulingEvent) -> SchedulingEvent:
        if not isinstance(event, SchedulingEvent):
            raise TypeError("EventStore.append requires a SchedulingEvent")
        self._events.append(event)
        return event

    def __iter__(self) -> Iterator[SchedulingEvent]:
        return iter(self._events)

    def __len__(self) -> int:
        return len(self._events)

    def __getitem__(self, index: int) -> SchedulingEvent:
        return self._events[index]

    @property
    def events(self) -> list[SchedulingEvent]:
        """Return a shallow copy of the event list (read-only view)."""
        return list(self._events)

    def export(self) -> list[dict[str, Any]]:
        """Deterministic serialization of the event stream."""
        return [e.model_dump(mode="json") for e in self._events]

    @classmethod
    def import_events(cls, data: list[dict[str, Any]]) -> "EventStore":
        """Reconstruct an EventStore from exported event dictionaries."""
        events = [SchedulingEvent.model_validate(item) for item in data]
        return cls(events)

    def sequence_position(self) -> int:
        """Number of events appended so far (0-based next index)."""
        return len(self._events)
