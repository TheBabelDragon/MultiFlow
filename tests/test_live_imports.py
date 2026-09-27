"""Ensure all advertised live package exports resolve."""

from __future__ import annotations


def test_live_package_exports():
    from multiflow.live import (
        CandidateScorer,
        DecisionRecord,
        DecisionSource,
        DeterministicCandidateScorer,
        EventStore,
        EventType,
        FeatureExtractor,
        LiveEngine,
        OperationalMetrics,
        ScheduleFeatures,
        ScheduleSnapshot,
        SchedulingEvent,
    )

    assert LiveEngine is not None
    assert EventStore is not None
    assert EventType is not None
    assert SchedulingEvent is not None
    assert ScheduleSnapshot is not None
    assert FeatureExtractor is not None
    assert ScheduleFeatures is not None
    assert CandidateScorer is not None
    assert DeterministicCandidateScorer is not None
    assert DecisionRecord is not None
    assert DecisionSource is not None
    assert OperationalMetrics is not None


def test_top_level_reexports():
    import multiflow

    assert hasattr(multiflow, "LiveEngine")
    assert hasattr(multiflow, "SchedulingEvent")
    assert hasattr(multiflow, "EventType")
    assert hasattr(multiflow, "ScheduleSnapshot")
