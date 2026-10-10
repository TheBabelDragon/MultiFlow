"""Shared Evidence Contract — MultiFlow decision/outcome records."""

import pytest

from multiflow.evidence import (
    OutcomeStatus,
    ConstraintVersion,
    DecisionEvidence,
    build_decision_evidence,
    attach_evidence_ref,
    check_evidence_schema,
    decision_record_to_evidence,
)
from multiflow.live.decision import DecisionRecord, DecisionSource


def test_build_admitted():
    ev = build_decision_evidence(
        snapshot_id="snap-1",
        proposed_candidate_ids=["c1", "c2"],
        admitted_candidate_id="c1",
        rejected_candidate_ids=["c2"],
        rejection_reasons={"c2": "capacity"},
        outcome_status=OutcomeStatus.ADMITTED,
        constraint_versions=[
            ConstraintVersion(constraint_id="no_overlap", version="1.0"),
        ],
        solver_id="classical",
        solver_version="0.2.0",
    )
    assert ev.admitted_candidate_id == "c1"
    assert ev.outcome_status == OutcomeStatus.ADMITTED
    assert len(ev.constraint_versions) == 1
    check_evidence_schema(ev)


def test_admitted_requires_candidate():
    with pytest.raises(ValueError):
        build_decision_evidence(
            snapshot_id="s",
            outcome_status=OutcomeStatus.ADMITTED,
            admitted_candidate_id=None,
        )


def test_solver_proposals_separate_from_admitted():
    ev = build_decision_evidence(
        snapshot_id="s",
        proposed_candidate_ids=["a", "b", "c"],
        admitted_candidate_id="a",
        outcome_status=OutcomeStatus.ADMITTED,
    )
    assert set(ev.proposed_candidate_ids) == {"a", "b", "c"}
    assert ev.admitted_candidate_id == "a"
    assert "b" in ev.proposed_candidate_ids


def test_override_preserves_history():
    original = build_decision_evidence(
        snapshot_id="s",
        proposed_candidate_ids=["a", "b"],
        admitted_candidate_id="a",
        outcome_status=OutcomeStatus.ADMITTED,
    )
    override = build_decision_evidence(
        snapshot_id="s",
        proposed_candidate_ids=["a", "b"],
        admitted_candidate_id="b",
        outcome_status=OutcomeStatus.OVERRIDE,
        human_override=True,
        override_reason="ops preference",
        override_of_decision_id=original.decision_id,
    )
    assert override.human_override
    assert override.override_of_decision_id == original.decision_id
    assert override.admitted_candidate_id == "b"
    assert original.admitted_candidate_id == "a"


def test_no_solution():
    ev = build_decision_evidence(
        snapshot_id="s",
        proposed_candidate_ids=[],
        outcome_status=OutcomeStatus.NO_SOLUTION,
    )
    assert ev.admitted_candidate_id is None
    assert ev.outcome_status == OutcomeStatus.NO_SOLUTION


def test_evidence_ref_upstream():
    ev = build_decision_evidence(
        snapshot_id="s",
        admitted_candidate_id="c1",
        outcome_status=OutcomeStatus.ADMITTED,
    )
    ev = attach_evidence_ref(
        ev,
        event_id="node|0x100|temp|1",
        source_id="temp_sensor_01",
        schema_id="tensorgate.lineage",
        schema_version="0.1.0",
    )
    assert len(ev.evidence_refs) == 1
    assert ev.evidence_refs[0]["schema_id"] == "tensorgate.lineage"


def test_roundtrip_dict():
    ev = build_decision_evidence(
        snapshot_id="snap-9",
        proposed_candidate_ids=["x"],
        admitted_candidate_id="x",
        outcome_status=OutcomeStatus.ADMITTED,
        constraint_versions=[ConstraintVersion(constraint_id="cap", version="2")],
    )
    d = ev.to_dict()
    ev2 = DecisionEvidence.from_dict(d)
    assert ev2.snapshot_id == "snap-9"
    assert ev2.admitted_candidate_id == "x"
    assert ev2.constraint_versions[0].constraint_id == "cap"
    check_evidence_schema(ev2)


def test_schema_major_mismatch():
    ev = build_decision_evidence(snapshot_id="s")
    ev = ev.model_copy(update={"schema_version": "1.0.0"})
    with pytest.raises(ValueError):
        check_evidence_schema(ev)


def test_from_decision_record():
    rec = DecisionRecord(
        snapshot_id="snap-r",
        selected_candidate_id="cand-1",
        source=DecisionSource.SOLVER,
        rejected_candidate_ids=["cand-2"],
        rejection_reasons={"cand-2": "overlap"},
        admissible_candidate_ids=["cand-1", "cand-2"],
        scores={"cand-1": 0.9, "cand-2": 0.4},
    )
    ev = decision_record_to_evidence(
        rec,
        constraint_versions=[ConstraintVersion(constraint_id="no_overlap", version="1")],
        solver_id="classical",
    )
    assert ev.admitted_candidate_id == "cand-1"
    assert ev.outcome_status == OutcomeStatus.ADMITTED
    assert "cand-2" in ev.rejected_candidate_ids
    assert "cand-1" in ev.proposed_candidate_ids
    check_evidence_schema(ev)


def test_live_engine_records_evidence_history():
    from pathlib import Path
    from multiflow import SchedulingProblem, LiveEngine, DecisionSource

    root = Path(__file__).resolve().parents[1]
    problem = SchedulingProblem.from_json(str(root / "examples" / "simple.json"))
    engine = LiveEngine(initial_problem=problem)
    result = engine.recalculate()
    selected = None
    if result["admissible"]:
        selected = result["admissible"][0].id
    engine.record_decision(
        selected_candidate_id=selected,
        source=DecisionSource.SOLVER,
    )
    assert len(engine.decision_history) == 1
    assert len(engine.evidence_history) == 1
    ev = engine.evidence_history[0]
    assert ev.snapshot_id == engine.decision_history[0].snapshot_id
    if selected:
        assert ev.admitted_candidate_id == selected
