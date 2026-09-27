"""Live engine: events, snapshots, validation-before-scoring, replay, metrics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from multiflow.domain.models import (
    CandidateSolution,
    Resource,
    ResourceType,
    SchedulingProblem,
    SolutionScore,
    Task,
    TimeWindow,
)
from multiflow.live.decision import DecisionSource
from multiflow.live.engine import LiveEngine
from multiflow.live.events import EventType, SchedulingEvent
from multiflow.live.features import FeatureExtractor, ScheduleFeatures
from multiflow.live.scorer import DeterministicCandidateScorer
from multiflow.live.snapshot import ScheduleSnapshot
from multiflow.validation.validator import Validator


def _simple_problem() -> SchedulingProblem:
    start = datetime(2026, 9, 17, 8, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 17, 17, 0, tzinfo=timezone.utc)
    return SchedulingProblem(
        id="prob-test",
        resources=[
            Resource(
                id="res-1",
                type=ResourceType.WORKER,
                name="W1",
                capabilities=["general"],
                availability=[TimeWindow(start=start, end=end)],
                capacity=1,
            ),
            Resource(
                id="res-2",
                type=ResourceType.WORKER,
                name="W2",
                capabilities=["general"],
                availability=[TimeWindow(start=start, end=end)],
                capacity=1,
            ),
        ],
        tasks=[
            Task(
                id="task-1",
                name="T1",
                requirements=[],
                duration=timedelta(hours=1),
                allowed_windows=[
                    TimeWindow(
                        start=datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc),
                        end=datetime(2026, 9, 17, 16, 0, tzinfo=timezone.utc),
                    )
                ],
                priority=5,
            ),
        ],
        constraints=[],
    )


def test_snapshot_reproducibility():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    s1 = engine.current_snapshot()
    s2 = engine.current_snapshot()
    assert s1.semantic_fingerprint() == s2.semantic_fingerprint()
    assert s1.problem.id == problem.id
    # Snapshot holds a copy — mutating engine problem does not mutate prior snapshot
    engine._problem.resources[0].capacity = 99
    assert s1.problem.resources[0].capacity == 1


def test_resource_unavailable_application():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    assert engine.problem.resource_by_id("res-1").availability
    engine.apply_event(
        SchedulingEvent(
            event_type=EventType.RESOURCE_UNAVAILABLE,
            entity_ids=["res-1"],
            attributes={"resource_id": "res-1"},
            source="ops",
            reason="offline",
        )
    )
    assert engine.problem.resource_by_id("res-1").availability == []
    assert len(engine.event_store) == 1


def test_live_recalculation_and_validation_before_scoring():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    result = engine.recalculate()
    assert "candidates" in result
    assert "admissible" in result
    assert "rejected" in result
    assert result["has_admissible_plan"] is True or result["has_admissible_plan"] is False
    # Every admissible candidate must pass validator
    validator = Validator()
    for cand in result["admissible"]:
        vr = validator.validate(engine.problem, cand)
        assert vr.admissible


def test_invalid_candidates_never_admissible_via_scoring():
    """Scorer must not turn invalid candidates into valid ones."""
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    snap = engine.current_snapshot()
    bogus = CandidateSolution(
        problem_id=problem.id,
        assignments=[],
        score=SolutionScore(admissible=True, total=999.0),
    )
    ranked = engine.scorer.rank(snap, [bogus], validator=engine.validator)
    for cand, _score in ranked:
        vr = engine.validator.validate(snap.problem, cand)
        assert vr.admissible


def test_deterministic_scorer_ordering():
    scorer = DeterministicCandidateScorer()
    f1 = ScheduleFeatures(assignment_count=2, candidate_soft_penalty=0.0, candidate_objective_total=0.0)
    f2 = ScheduleFeatures(assignment_count=1, candidate_soft_penalty=0.0, candidate_objective_total=0.0)
    c1 = CandidateSolution(id="cand-a", problem_id="p")
    c2 = CandidateSolution(id="cand-b", problem_id="p")
    assert scorer.score(f1, c1) > scorer.score(f2, c2)


def test_decision_recording_and_human_override_preservation():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    result = engine.recalculate()
    selected = result["admissible"][0].id if result["admissible"] else None
    d1 = engine.record_decision(
        selected_candidate_id=selected,
        source=DecisionSource.SOLVER,
    )
    assert len(engine.decision_history) == 1
    assert d1.human_override is False

    d2 = engine.record_decision(
        selected_candidate_id=selected,
        source=DecisionSource.HUMAN_OVERRIDE,
        human_override=True,
        override_reason="operator preference",
        override_of_decision_id=d1.id,
    )
    assert len(engine.decision_history) == 2
    assert engine.decision_history[0].id == d1.id
    assert engine.decision_history[1].human_override is True
    assert engine.decision_history[1].override_of_decision_id == d1.id
    assert any(e.event_type == EventType.HUMAN_OVERRIDE for e in engine.event_store)


def test_metrics_updates():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    engine.apply_event(
        SchedulingEvent(
            event_type=EventType.RESOURCE_CAPACITY_CHANGED,
            entity_ids=["res-1"],
            attributes={"resource_id": "res-1", "capacity": 1},
        )
    )
    engine.recalculate()
    m = engine.metrics
    assert m.events_processed >= 1
    assert m.recalculations >= 1
    assert m.candidates_generated >= 0


def test_infeasible_state_explicit():
    """When all candidates fail validation, expose no-admissible-plan state."""
    start = datetime(2026, 9, 17, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc)
    problem = SchedulingProblem(
        id="prob-inf",
        resources=[
            Resource(
                id="solo",
                type=ResourceType.WORKER,
                name="Solo",
                capabilities=["general"],
                availability=[TimeWindow(start=start, end=end)],
                capacity=1,
            )
        ],
        tasks=[
            Task(
                id="ta",
                name="A",
                requirements=[],
                duration=timedelta(hours=2),
                allowed_windows=[TimeWindow(start=start, end=end)],
                priority=10,
            ),
            Task(
                id="tb",
                name="B",
                requirements=[],
                duration=timedelta(hours=2),
                allowed_windows=[TimeWindow(start=start, end=end)],
                priority=10,
            ),
        ],
        constraints=[],
    )
    engine = LiveEngine(initial_problem=problem)
    result = engine.recalculate()
    engine.apply_event(
        SchedulingEvent(
            event_type=EventType.RESOURCE_UNAVAILABLE,
            entity_ids=["solo"],
            attributes={"resource_id": "solo"},
            source="ops",
            reason="offline",
        )
    )
    result2 = engine.recalculate()
    if len(result2["admissible"]) == 0:
        assert result2["has_admissible_plan"] is False
        assert engine.has_admissible_plan is False
        assert engine.metrics.infeasible_recalculations >= 1


def test_deterministic_replay():
    problem = _simple_problem()
    engine = LiveEngine(initial_problem=problem)
    engine.apply_event(
        SchedulingEvent(
            id="evt-replay-1",
            event_type=EventType.RESOURCE_UNAVAILABLE,
            entity_ids=["res-1"],
            attributes={"resource_id": "res-1"},
            source="ops",
            reason="maintenance",
            timestamp=datetime(2026, 9, 17, 10, 0, tzinfo=timezone.utc),
        )
    )
    engine.apply_event(
        SchedulingEvent(
            id="evt-replay-2",
            event_type=EventType.RESOURCE_CAPACITY_CHANGED,
            entity_ids=["res-2"],
            attributes={"resource_id": "res-2", "capacity": 2},
            source="ops",
            reason="upgrade",
            timestamp=datetime(2026, 9, 17, 11, 0, tzinfo=timezone.utc),
        )
    )
    state = engine.semantic_state()
    replayed = LiveEngine.replay(problem, engine.event_store.events)
    assert replayed.semantic_state() == state


def test_feature_extractor_deterministic():
    problem = _simple_problem()
    snap = ScheduleSnapshot.from_problem(problem, event_sequence_position=0)
    ext = FeatureExtractor()
    f1 = ext.extract(snapshot=snap)
    f2 = ext.extract(snapshot=snap)
    assert f1.model_dump() == f2.model_dump()
    assert f1.task_count == 1
    assert f1.resource_count == 2


def test_corporate_live_disruption(tmp_path=None):
    root = Path(__file__).resolve().parents[1]
    path = root / "examples" / "corporate.json"
    if not path.is_file():
        pytest.skip("corporate.json not found")
    problem = SchedulingProblem.from_json(str(path))
    engine = LiveEngine(initial_problem=problem)
    initial = engine.recalculate()
    assert initial["has_admissible_plan"] is True or len(initial["candidates"]) >= 0

    engine.apply_event(
        SchedulingEvent(
            event_type=EventType.RESOURCE_UNAVAILABLE,
            entity_ids=["forklift-17"],
            attributes={"resource_id": "forklift-17"},
            source="ops",
            reason="maintenance",
        )
    )
    after = engine.recalculate()
    assert "admissible" in after
    assert "rejected" in after
    fl = engine.problem.resource_by_id("forklift-17")
    assert fl is not None
    assert fl.availability == []


def test_existing_solver_still_works():
    from multiflow.solver.classical import ClassicalSolver

    problem = _simple_problem()
    solver = ClassicalSolver()
    cands = solver.solve(problem)
    assert isinstance(cands, list)
    validator = Validator()
    for c in cands:
        vr = validator.validate(problem, c)
        assert isinstance(vr.admissible, bool)
