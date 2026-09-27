"""Event store append-only and event model tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from multiflow.live.events import EventStore, EventType, SchedulingEvent


def test_event_store_append_only():
    store = EventStore()
    e1 = SchedulingEvent(
        event_type=EventType.RESOURCE_UNAVAILABLE,
        entity_ids=["r1"],
        attributes={"resource_id": "r1"},
        source="ops",
        reason="maintenance",
    )
    e2 = SchedulingEvent(
        event_type=EventType.TASK_ARRIVED,
        entity_ids=["t1"],
        attributes={"task_id": "t1"},
        source="system",
    )
    store.append(e1)
    store.append(e2)
    assert len(store) == 2
    assert store[0].event_type == EventType.RESOURCE_UNAVAILABLE
    assert store[1].event_type == EventType.TASK_ARRIVED

    with pytest.raises((TypeError, AttributeError)):
        store.events = []  # type: ignore[misc]


def test_scheduling_event_defaults():
    e = SchedulingEvent(event_type=EventType.SCHEDULE_CHANGED)
    assert e.id
    assert e.timestamp is not None
    assert e.entity_ids == []
    assert e.attributes == {}
    assert e.source == "system"


def test_event_types_complete():
    expected = {
        "RESOURCE_UNAVAILABLE",
        "RESOURCE_AVAILABLE",
        "RESOURCE_CAPACITY_CHANGED",
        "TASK_ARRIVED",
        "TASK_CANCELLED",
        "TASK_UPDATED",
        "ASSIGNMENT_LOCKED",
        "CONSTRAINT_CHANGED",
        "SCHEDULE_CHANGED",
        "HUMAN_OVERRIDE",
        "HORIZON_CHANGED",
    }
    actual = {et.name for et in EventType}
    assert expected.issubset(actual)
