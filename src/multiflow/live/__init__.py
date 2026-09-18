"""Live operation / event-learning layer for MultiFlow.

This package adds:

* immutable SchedulingEvent stream
* ScheduleSnapshot (reproducible solver input)
* live recalculation loop
* CandidateScorer (preference only; Validator remains correctness authority)
* DecisionRecord (solver vs human vs outcome)
* ScheduleFeatures (stable boundary for future learned ranking)
* deterministic replay
* operational metrics

The neural system is expected to enter only at:

    ScheduleFeatures → CandidateScorer → ranking → existing Validator

It must never invent schedules.
"""

from multiflow.live.decision import DecisionRecord, DecisionSource
from multiflow.live.engine import LiveEngine
from multiflow.live.events import EventStore, EventType, SchedulingEvent
from multiflow.live.features import FeatureExtractor, ScheduleFeatures
from multiflow.live.metrics import OperationalMetrics
from multiflow.live.scorer import CandidateScorer, DeterministicCandidateScorer
from multiflow.live.snapshot import ScheduleSnapshot

__all__ = [
    "SchedulingEvent",
    "EventType",
    "EventStore",
    "ScheduleSnapshot",
    "ScheduleFeatures",
    "FeatureExtractor",
    "CandidateScorer",
    "DeterministicCandidateScorer",
    "DecisionRecord",
    "DecisionSource",
    "OperationalMetrics",
    "LiveEngine",
]
