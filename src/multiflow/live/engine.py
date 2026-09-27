"""Live adaptive scheduling engine.

Architectural invariant:
  MultiFlow owns the problem definition and correctness.
  Solvers only propose solutions.
  Validator is the sole authority for candidate admissibility.
  CandidateScorer may rank admissible candidates; it never establishes correctness.
"""

from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from multiflow.domain.models import (
    Assignment,
    CandidateSolution,
    Resource,
    SchedulingProblem,
    Task,
    TimeWindow,
)
from multiflow.live.decision import DecisionRecord, DecisionSource
from multiflow.live.events import EventStore, EventType, SchedulingEvent
from multiflow.live.features import FeatureExtractor
from multiflow.live.metrics import OperationalMetrics
from multiflow.live.scorer import CandidateScorer, DeterministicCandidateScorer
from multiflow.live.snapshot import ScheduleSnapshot
from multiflow.solver.classical import ClassicalSolver
from multiflow.solver.interface import Solver
from multiflow.validation.validator import Validator


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LiveEngine:
    """Operational engine that applies events, snapshots, solves, validates, ranks."""

    def __init__(
        self,
        initial_problem: SchedulingProblem,
        solver: Optional[Solver] = None,
        validator: Optional[Validator] = None,
        scorer: Optional[CandidateScorer] = None,
    ) -> None:
        self._initial_problem = SchedulingProblem.model_validate(
            initial_problem.model_dump()
        )
        self._problem = SchedulingProblem.model_validate(initial_problem.model_dump())
        self.solver: Solver = solver or ClassicalSolver()
        self.validator = validator or Validator()
        self.scorer: CandidateScorer = scorer or DeterministicCandidateScorer()
        self.feature_extractor = FeatureExtractor(validator=self.validator)
        self.event_store = EventStore()
        self.decision_history: list[DecisionRecord] = []
        self.metrics = OperationalMetrics()
        self._last_candidates: list[CandidateSolution] = []
        self._last_validation: dict[str, Any] = {}
        self._last_admissible: list[CandidateSolution] = []
        self._last_rejected: dict[str, str] = {}
        self._last_ranked: list[tuple[CandidateSolution, float]] = []
        self._has_admissible_plan: bool = True
        self._last_snapshot: Optional[ScheduleSnapshot] = None

    def apply_event(self, event: SchedulingEvent) -> SchedulingEvent:
        """Append event, apply supported operational change, return the event."""
        stored = self.event_store.append(event)
        self.metrics.record_event()
        self._apply_event_to_state(event)
        return stored

    def current_snapshot(self) -> ScheduleSnapshot:
        """Deterministic snapshot of current normalized problem state."""
        snap = ScheduleSnapshot.from_problem(
            self._problem,
            event_sequence_position=self.event_store.sequence_position(),
            event_ids=[e.id for e in self.event_store.events],
        )
        self._last_snapshot = snap
        return snap

    def recalculate(self) -> dict[str, Any]:
        """Solve -> validate every candidate -> rank admissible -> update metrics.

        Returns a structured result describing candidates, admissibility,
        and whether an admissible plan exists.
        """
        snapshot = self.current_snapshot()
        t0 = time.perf_counter()
        candidates = list(self.solver.solve(snapshot.problem))
        solver_runtime = time.perf_counter() - t0

        t1 = time.perf_counter()
        admissible: list[CandidateSolution] = []
        rejected: dict[str, str] = {}
        validation_details: dict[str, Any] = {}
        for cand in candidates:
            vr = self.validator.validate(snapshot.problem, cand)
            validation_details[cand.id] = {
                "admissible": vr.admissible,
                "hard_violations": len(vr.hard_violations),
                "explanation_chain": list(vr.explanation_chain),
                "score": vr.score.model_dump(mode="json"),
            }
            if vr.admissible:
                cand.score = vr.score
                admissible.append(cand)
            else:
                reason = (
                    "; ".join(vr.explanation_chain)
                    if vr.explanation_chain
                    else f"{len(vr.hard_violations)} hard violation(s)"
                )
                rejected[cand.id] = reason
        validation_runtime = time.perf_counter() - t1

        ranked = self.scorer.rank(
            snapshot,
            candidates,
            validator=self.validator,
            extractor=self.feature_extractor,
        )

        infeasible = len(admissible) == 0
        self.metrics.record_recalculation(
            candidates=len(candidates),
            admissible=len(admissible),
            rejected=len(rejected),
            solver_runtime=solver_runtime,
            validation_runtime=validation_runtime,
            infeasible=infeasible,
        )

        self._last_candidates = candidates
        self._last_validation = validation_details
        self._last_admissible = admissible
        self._last_rejected = rejected
        self._last_ranked = ranked
        self._has_admissible_plan = not infeasible

        return {
            "snapshot_id": snapshot.id,
            "event_sequence_position": snapshot.event_sequence_position,
            "candidates": candidates,
            "admissible": admissible,
            "rejected": rejected,
            "ranked": ranked,
            "has_admissible_plan": not infeasible,
            "validation": validation_details,
            "solver_runtime_seconds": solver_runtime,
            "validation_runtime_seconds": validation_runtime,
        }

    def rank_candidates(
        self, snapshot: Optional[ScheduleSnapshot] = None
    ) -> list[tuple[CandidateSolution, float]]:
        """Rank admissible candidates for a snapshot (or last recalculation)."""
        if snapshot is None:
            if self._last_ranked:
                return list(self._last_ranked)
            snapshot = self.current_snapshot()
            candidates = list(self.solver.solve(snapshot.problem))
        else:
            candidates = list(self.solver.solve(snapshot.problem))
        ranked = self.scorer.rank(
            snapshot,
            candidates,
            validator=self.validator,
            extractor=self.feature_extractor,
        )
        self._last_ranked = ranked
        return ranked

    def record_decision(
        self,
        selected_candidate_id: Optional[str] = None,
        source: DecisionSource = DecisionSource.SOLVER,
        snapshot_id: Optional[str] = None,
        rejected_candidate_ids: Optional[list[str]] = None,
        rejection_reasons: Optional[dict[str, str]] = None,
        human_override: bool = False,
        override_reason: str = "",
        override_of_decision_id: Optional[str] = None,
        resulting_event_id: Optional[str] = None,
        outcome: Optional[dict[str, Any]] = None,
        attributes: Optional[dict[str, Any]] = None,
        scores: Optional[dict[str, float]] = None,
    ) -> DecisionRecord:
        """Record a decision. Human overrides add history; never erase prior decisions."""
        snap_id = snapshot_id
        if snap_id is None:
            if self._last_snapshot is not None:
                snap_id = self._last_snapshot.id
            else:
                snap_id = self.current_snapshot().id

        rejected_ids = rejected_candidate_ids
        if rejected_ids is None:
            rejected_ids = list(self._last_rejected.keys())
        reasons = rejection_reasons if rejection_reasons is not None else dict(self._last_rejected)

        admissible_ids = [c.id for c in self._last_admissible]
        score_map = scores if scores is not None else {
            c.id: s for c, s in self._last_ranked
        }

        is_override = human_override or source == DecisionSource.HUMAN_OVERRIDE
        record = DecisionRecord(
            snapshot_id=snap_id,
            selected_candidate_id=selected_candidate_id,
            source=source if not is_override else DecisionSource.HUMAN_OVERRIDE,
            rejected_candidate_ids=list(rejected_ids),
            rejection_reasons=dict(reasons),
            human_override=is_override,
            override_reason=override_reason,
            override_of_decision_id=override_of_decision_id,
            resulting_event_id=resulting_event_id,
            outcome=dict(outcome or {}),
            attributes=dict(attributes or {}),
            admissible_candidate_ids=admissible_ids,
            scores=score_map,
        )
        self.decision_history.append(record)
        self.metrics.record_decision(is_override=is_override)

        if is_override:
            override_event = SchedulingEvent(
                event_type=EventType.HUMAN_OVERRIDE,
                entity_ids=[selected_candidate_id] if selected_candidate_id else [],
                attributes={
                    "decision_id": record.id,
                    "selected_candidate_id": selected_candidate_id,
                    "override_of_decision_id": override_of_decision_id,
                },
                source="human",
                reason=override_reason or "human override",
            )
            self.event_store.append(override_event)
            self.metrics.record_event()
            record.resulting_event_id = override_event.id

        return record

    @classmethod
    def replay(
        cls,
        initial_problem: SchedulingProblem,
        event_stream: Sequence[SchedulingEvent],
        solver: Optional[Solver] = None,
        validator: Optional[Validator] = None,
        scorer: Optional[CandidateScorer] = None,
    ) -> "LiveEngine":
        """Reproduce operational state from initial problem + ordered events."""
        engine = cls(
            initial_problem=initial_problem,
            solver=solver,
            validator=validator,
            scorer=scorer,
        )
        for event in event_stream:
            engine.apply_event(
                SchedulingEvent(
                    id=event.id,
                    schema_version=event.schema_version,
                    event_type=event.event_type,
                    entity_ids=list(event.entity_ids),
                    attributes=dict(event.attributes),
                    source=event.source,
                    reason=event.reason,
                    timestamp=event.timestamp,
                )
            )
        return engine

    @property
    def problem(self) -> SchedulingProblem:
        return self._problem

    @property
    def has_admissible_plan(self) -> bool:
        return self._has_admissible_plan

    @property
    def last_candidates(self) -> list[CandidateSolution]:
        return list(self._last_candidates)

    @property
    def last_admissible(self) -> list[CandidateSolution]:
        return list(self._last_admissible)

    @property
    def last_rejected(self) -> dict[str, str]:
        return dict(self._last_rejected)

    @property
    def last_validation(self) -> dict[str, Any]:
        return dict(self._last_validation)

    def semantic_state(self) -> dict[str, Any]:
        """Semantic comparison key for deterministic replay assertions."""
        p = self._problem
        return {
            "problem_id": p.id,
            "resource_ids": sorted(r.id for r in p.resources),
            "resource_availability": {
                r.id: [
                    (w.start.isoformat(), w.end.isoformat()) for w in r.availability
                ]
                for r in sorted(p.resources, key=lambda x: x.id)
            },
            "resource_capacity": {
                r.id: r.capacity for r in sorted(p.resources, key=lambda x: x.id)
            },
            "task_ids": sorted(t.id for t in p.tasks),
            "task_priorities": {
                t.id: t.priority for t in sorted(p.tasks, key=lambda x: x.id)
            },
            "event_count": len(self.event_store),
            "event_types": [e.event_type.value for e in self.event_store],
        }

    def _apply_event_to_state(self, event: SchedulingEvent) -> None:
        et = event.event_type
        attrs = event.attributes or {}

        if et == EventType.RESOURCE_UNAVAILABLE:
            rid = attrs.get("resource_id") or (
                event.entity_ids[0] if event.entity_ids else None
            )
            if rid:
                self._set_resource_unavailable(rid, attrs)

        elif et == EventType.RESOURCE_AVAILABLE:
            rid = attrs.get("resource_id") or (
                event.entity_ids[0] if event.entity_ids else None
            )
            if rid:
                self._set_resource_available(rid, attrs)

        elif et == EventType.RESOURCE_CAPACITY_CHANGED:
            rid = attrs.get("resource_id") or (
                event.entity_ids[0] if event.entity_ids else None
            )
            if rid is not None and "capacity" in attrs:
                self._set_resource_capacity(rid, int(attrs["capacity"]))

        elif et == EventType.TASK_ADDED:
            task_data = attrs.get("task")
            if task_data:
                task = Task.model_validate(task_data)
                if self._problem.task_by_id(task.id) is None:
                    self._problem.tasks.append(task)

        elif et == EventType.TASK_REMOVED:
            tid = attrs.get("task_id") or (
                event.entity_ids[0] if event.entity_ids else None
            )
            if tid:
                self._problem.tasks = [t for t in self._problem.tasks if t.id != tid]
                self._problem.existing_assignments = [
                    a for a in self._problem.existing_assignments if a.task_id != tid
                ]

        elif et == EventType.TASK_CHANGED:
            tid = attrs.get("task_id") or (
                event.entity_ids[0] if event.entity_ids else None
            )
            if tid and "updates" in attrs:
                self._update_task(tid, attrs["updates"])

        elif et == EventType.ASSIGNMENT_CHANGED:
            if "assignments" in attrs:
                new_asgs = [
                    Assignment.model_validate(a) for a in attrs["assignments"]
                ]
                self._problem.existing_assignments = new_asgs
            elif "clear" in attrs and attrs["clear"]:
                self._problem.existing_assignments = []

        elif et == EventType.CONSTRAINT_CHANGED:
            self._problem.attributes = dict(self._problem.attributes or {})
            self._problem.attributes.setdefault("constraint_change_events", []).append(
                event.id
            )

        elif et == EventType.SCHEDULE_CHANGED:
            self._problem.attributes = dict(self._problem.attributes or {})
            self._problem.attributes.setdefault("schedule_change_events", []).append(
                event.id
            )

        elif et == EventType.HUMAN_OVERRIDE:
            pass

    def _set_resource_unavailable(self, resource_id: str, attrs: dict[str, Any]) -> None:
        res = self._problem.resource_by_id(resource_id)
        if res is None:
            return
        res.attributes = dict(res.attributes or {})
        res.attributes.setdefault("_prior_capacity", res.capacity)
        res.attributes["unavailable"] = True
        if "unavailable_window" in attrs:
            uw = TimeWindow.model_validate(attrs["unavailable_window"])
            new_avail: list[TimeWindow] = []
            for a in res.availability:
                if not a.overlaps(uw):
                    new_avail.append(a)
                else:
                    if a.start < uw.start:
                        new_avail.append(
                            TimeWindow(start=a.start, end=min(a.end, uw.start))
                        )
                    if a.end > uw.end:
                        new_avail.append(
                            TimeWindow(start=max(a.start, uw.end), end=a.end)
                        )
            new_avail = [w for w in new_avail if w.end > w.start]
            res.availability = new_avail
        else:
            res.availability = []
            res.capacity = 0
        self._problem.existing_assignments = [
            a
            for a in self._problem.existing_assignments
            if resource_id not in a.resource_ids
        ]

    def _set_resource_available(self, resource_id: str, attrs: dict[str, Any]) -> None:
        res = self._problem.resource_by_id(resource_id)
        if res is None:
            return
        res.attributes = dict(res.attributes or {})
        res.attributes["unavailable"] = False
        prior = res.attributes.get("_prior_capacity")
        if prior is not None and res.capacity == 0:
            res.capacity = int(prior)
        if "availability" in attrs:
            windows = [TimeWindow.model_validate(w) for w in attrs["availability"]]
            res.availability = windows
        elif "available_window" in attrs:
            w = TimeWindow.model_validate(attrs["available_window"])
            res.availability = list(res.availability) + [w]

    def _set_resource_capacity(self, resource_id: str, capacity: int) -> None:
        res = self._problem.resource_by_id(resource_id)
        if res is None:
            return
        res.capacity = max(0, capacity)

    def _update_task(self, task_id: str, updates: dict[str, Any]) -> None:
        task = self._problem.task_by_id(task_id)
        if task is None:
            return
        data = task.model_dump()
        data.update(updates)
        updated = Task.model_validate(data)
        self._problem.tasks = [
            updated if t.id == task_id else t for t in self._problem.tasks
        ]
