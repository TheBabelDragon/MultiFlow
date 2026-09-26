"""Event store: append-only, serialization, reconstruction."""

from datetime import datetime, timezone

import pytest

from multiflow.live.events import EventStore, EventType, SchedulingEvent


def test_event_append_only():
    store = EventStore()
    e1 = SchedulingEvent(
        event_type=EventType.RESOURCE_UNAVAILABLE,
        entity_ids=["r1"],
        attributes={"resource_id": "r1"},
        source="ops",
        reason="maintenance",
    )
    store.append(e1)
    assert len(store) == 1
    e2 = SchedulingEvent(
        event_type=EventType.TASK_ADDED,
        entity_ids=["t1"],
        source="ops",
    )
    store.append(e2)
    assert len(store) == 2
    assert list(store)[0].id == e1.id
    assert list(store)[1].id == e2.id


def test_event_immutable():
    e = SchedulingEvent(
        event_type=EventType.RESOURCE_AVAILABLE,
        entity_ids=["r1"],
    )
    with pytest.raises(Exception):
        e.reason = "changed"  # type: ignore[misc]


def test_event_serialization_roundtrip():
    store = EventStore()
    ts = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)
    e = SchedulingEvent(
        id="evt-fixed",
        event_type=EventType.RESOURCE_CAPACITY_CHANGED,
        entity_ids=["r1"],
        attributes={"resource_id": "r1", "capacity": 2},
        source="ops",
        reason="upgrade",
        timestamp=ts,
    )
    store.append(e)
    exported = store.export()
    restored = EventStore.import_events(exported)
    assert len(restored) == 1
    r = restored[0]
    assert r.id == "evt-fixed"
    assert r.event_type == EventType.RESOURCE_CAPACITY_CHANGED
    assert r.attributes["capacity"] == 2
    assert r.timestamp == ts


def test_no_removal_api():
    store = EventStore()
    store.append(
        SchedulingEvent(event_type=EventType.SCHEDULE_CHANGED, entity_ids=[])
    )
    assert not hasattr(store, "remove")
    assert not hasattr(store, "pop")
    assert not hasattr(store, "clear")
