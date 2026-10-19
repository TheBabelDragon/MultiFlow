"""Versioned scheduling API tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from multiflow.api import (
    API_SCHEMA_VERSION,
    SchedulingApi,
    SchedulingRequest,
    SchedulingStatus,
)
from multiflow.domain.models import Resource, ResourceType, SchedulingProblem, Task, TimeWindow


def _minimal_problem() -> dict:
    now = datetime.now(timezone.utc)
    w = TimeWindow(start=now, end=now + timedelta(hours=2))
    problem = SchedulingProblem(
        resources=[
            Resource(
                id="worker-1",
                type=ResourceType.WORKER,
                name="w1",
                capabilities=["compute"],
                availability=[w],
                capacity=1,
            )
        ],
        tasks=[
            Task(id="task-1", name="t1", requirements=[], window=w, attributes={}),
        ],
    )
    return problem.model_dump(mode="json")


def test_health():
    api = SchedulingApi()
    h = api.health()
    assert h.healthy is True
    assert h.schema_version == API_SCHEMA_VERSION
    assert "classical_solver" in h.capabilities


def test_negotiate_compatible():
    api = SchedulingApi()
    n = api.negotiate("1.0.0")
    assert n["compatible"] is True


def test_negotiate_incompatible_major():
    api = SchedulingApi()
    n = api.negotiate("9.0.0")
    assert n["compatible"] is False


def test_invalid_request_empty_problem():
    api = SchedulingApi()
    resp = api.schedule(SchedulingRequest(problem={}))
    assert resp.status == SchedulingStatus.INVALID_REQUEST


def test_invalid_schema_major():
    with pytest.raises(Exception):
        SchedulingRequest(schema_version="2.0.0", problem=_minimal_problem())


def test_schedule_admitted_or_no_solution():
    api = SchedulingApi()
    resp = api.schedule(SchedulingRequest(problem=_minimal_problem()))
    assert resp.status in (
        SchedulingStatus.ADMITTED,
        SchedulingStatus.PROPOSED,
        SchedulingStatus.NO_COMPLETE_SOLUTION,
    )
    assert resp.solver_identity


def test_idempotent_correlation():
    api = SchedulingApi()
    req = SchedulingRequest(problem=_minimal_problem(), correlation_id="corr-fixed-1")
    r1 = api.schedule(req)
    r2 = api.schedule(req)
    assert r1.correlation_id == r2.correlation_id
    assert r2.attributes.get("idempotent_replay") is True


def test_stale_snapshot():
    api = SchedulingApi()
    resp = api.schedule(
        SchedulingRequest(
            problem=_minimal_problem(),
            snapshot_version="snap-a",
            expected_snapshot_version="snap-b",
        )
    )
    assert resp.status == SchedulingStatus.STALE_SNAPSHOT
