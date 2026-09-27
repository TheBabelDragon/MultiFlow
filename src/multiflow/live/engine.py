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
)
from multiflow.live.decision import DecisionRecord, DecisionSource
from multiflow.live.events import EventStore, EventType, SchedulingEvent
from multiflow.live.features import FeatureExtractor, ScheduleFeatures
from multiflow.live.metrics import OperationalMetrics
from multiflow.live.scorer import CandidateScorer, DeterministicCandidateScorer
from multiflow.live.snapshot import ScheduleSnapshot
from multiflow.solver.base import Solver
from multiflow.solver.fabric import SolverFabric
from multiflow.validator.validator import Validator


class LiveEngine:
    """Owns normalized problem state, applies domain events, and drives the
    solver fabric under the validation-before-scoring invariant.

    Flow:
      LIVE DOMAIN EVENTS
        -> NORMALIZED STATE
        -> SNAPSHOT
        -> SOLVER FABRIC
        -> CANDIDATES
        -> VALIDATOR
        -> ADMISSIBLE PLANS
        -> DECISION/OVERRIDE
        -> RESULTING STATE
        -> EVENT HISTORY
    """

    def __init__(
        self,
        problem: SchedulingProblem,
        *,
        solver: Optional[Solver] = None,
        fabric: Optional[SolverFabric] = None,
        validator: Optional[Validator] = None,
        scorer: Optional[CandidateScorer] = None,
        event_store: Optional[EventStore] = None,
        metrics: Optional[OperationalMetrics] = None,
    ) -> None:
        self._problem = problem.model_copy(deep=True)
        self._validator = validator or Validator()
        self._scorer = scorer or DeterministicCandidateScorer()
        self._event_store = event_store or EventStore()
        self._metrics = metrics or OperationalMetrics()
        self._fabric = fabric
        self._solver = solver
        if self._fabric is None and self._solver is None:
            from multiflow.solver.classical import ClassicalSolver

            self._solver = ClassicalSolver()
        self._last_snapshot: Optional[ScheduleSnapshot] = None
        self._last_admissible: list[CandidateSolution] = []
        self._last_ranked: list[tuple[CandidateSolution, float]] = []
        self._current_assignment: Optional[Assignment] = None
        self._decision_history: list[DecisionRecord] = []

    @property
    def problem(self) -> SchedulingProblem:
        return self._problem.model_copy(deep=True)

    @property
    def event_store(self) -> EventStore:
        return self._event_store

    @property
    def metrics(self) -> OperationalMetrics:
        return self._metrics

    @property
    def decision_history(self) -> list[DecisionRecord]:
        return list(self._decision_history)

    @property
    def last_admissible(self) -> list[CandidateSolution]:
        return list(self._last_admissible)

    @property
    def last_ranked(self) -> list[tuple[CandidateSolution, float]]:
        return list(self._last_ranked)

    def apply_event(self, event: SchedulingEvent) -> None:
        """Append event and mutate normalized state deterministically."""
        self._event_store.append(event)
        self._apply_event_to_state(event)
        self._metrics.record_event(event.event_type.value)

    def recalculate(
        self,
        *,
        max_candidates: int = 5,
        time_limit_s: Optional[float] = None,
    ) -> dict[str, Any]:
        """Produce snapshot, propose candidates, validate, rank admissible only.

        Returns a result dict with admissible plans, ranked list, and
        infeasibility flag when no candidate survives validation.
        """
        t0 = time.perf_counter()
        snapshot = ScheduleSnapshot.from_problem(
            self._problem,
            event_count=len(self._event_store),
        )
        self._last_snapshot = snapshot

        candidates = self._propose_candidates(
            max_candidates=max_candidates,
            time_limit_s=time_limit_s,
        )
        self._metrics.record_candidates_proposed(len(candidates))

        admissible: list[CandidateSolution] = []
        for cand in candidates:
            report = self._validator.validate(self._problem, cand)
            if report.is_valid:
                admissible.append(cand)
            else:
                self._metrics.record_rejected()

        self._last_admissible = admissible
        self._metrics.record_admissible(len(admissible))

        ranked = self._scorer.rank(admissible, self._problem) if admissible else []
        self._last_ranked = ranked

        elapsed = time.perf_counter() - t0
        self._metrics.record_recalculate(elapsed)

        infeasible = len(admissible) == 0
        if infeasible:
            self._metrics.record_infeasible()

        return {
            "snapshot_id": snapshot.snapshot_id,
            "semantic_fingerprint": snapshot.semantic_fingerprint,
            "candidates_proposed": len(candidates),
            "admissible_count": len(admissible),
            "admissible": [c.model_dump() for c in admissible],
            "ranked": [
                {"candidate": c.model_dump(), "score": score} for c, score in ranked
            ],
            "infeasible": infeasible,
            "elapsed_s": elapsed,
            "event_count": len(self._event_store),
        }

    def rank_candidates(
        self,
        candidates: Sequence[CandidateSolution],
    ) -> list[tuple[CandidateSolution, float]]:
        """Rank only after validation; never trusts solver feasibility."""
        admissible: list[CandidateSolution] = []
        for cand in candidates:
            report = self._validator.validate(self._problem, cand)
            if report.is_valid:
                admissible.append(cand)
        return self._scorer.rank(admissible, self._problem)

    def record_decision(
        self,
        *,
        source: DecisionSource,
        chosen: Optional[CandidateSolution] = None,
        reason: str = "",
        override_note: str = "",
    ) -> DecisionRecord:
        """Record a decision; human overrides also append a domain event."""
        record = DecisionRecord(
            source=source,
            chosen_candidate_id=chosen.candidate_id if chosen else None,
            reason=reason,
            override_note=override_note,
            timestamp=datetime.now(timezone.utc),
            event_count_at_decision=len(self._event_store),
        )
        self._decision_history.append(record)

        if source == DecisionSource.HUMAN_OVERRIDE and chosen is not None:
            event = SchedulingEvent(
                event_type=EventType.HUMAN_OVERRIDE,
                payload={
                    "candidate_id": chosen.candidate_id,
                    "reason": reason,
                    "override_note": override_note,
                },
            )
            self.apply_event(event)
            if chosen.assignments:
                # Apply first assignment as resulting state for simplicity
                self._current_assignment = chosen.assignments[0]

        self._metrics.record_decision(source.value)
        return record

    def replay(self, events: Sequence[SchedulingEvent]) -> SchedulingProblem:
        """Deterministically rebuild state from an event sequence."""
        # Reset to a clean copy of the original problem is not stored;
        # callers should construct a fresh engine for full replay from origin.
        for event in events:
            self._apply_event_to_state(event)
            self._event_store.append(event)
        return self.problem

    def semantic_state(self) -> dict[str, Any]:
        """Stable, ordered representation for deterministic replay tests."""
        return {
            "resources": [
                r.model_dump(mode="json")
                for r in sorted(self._problem.resources, key=lambda x: x.id)
            ],
            "tasks": [
                t.model_dump(mode="json")
                for t in sorted(self._problem.tasks, key=lambda x: x.id)
            ],
            "horizon": self._problem.horizon.model_dump(mode="json")
            if self._problem.horizon
            else None,
            "event_count": len(self._event_store),
        }

    def _propose_candidates(
        self,
        *,
        max_candidates: int,
        time_limit_s: Optional[float],
    ) -> list[CandidateSolution]:
        if self._fabric is not None:
            return list(
                self._fabric.solve(
                    self._problem,
                    max_candidates=max_candidates,
                    time_limit_s=time_limit_s,
                )
            )
        assert self._solver is not None
        result = self._solver.solve(
            self._problem,
            max_candidates=max_candidates,
            time_limit_s=time_limit_s,
        )
        if isinstance(result, CandidateSolution):
            return [result]
        return list(result)

    def _apply_event_to_state(self, event: SchedulingEvent) -> None:
        et = event.event_type
        payload = event.payload or {}

        if et == EventType.RESOURCE_UNAVAILABLE:
            rid = payload.get("resource_id")
            if rid:
                self._set_resource_availability(rid, available=False)

        elif et == EventType.RESOURCE_AVAILABLE:
            rid = payload.get("resource_id")
            if rid:
                self._set_resource_availability(rid, available=True)

        elif et == EventType.TASK_ARRIVED:
            task_data = payload.get("task")
            if task_data:
                task = Task.model_validate(task_data)
                if not any(t.id == task.id for t in self._problem.tasks):
                    self._problem.tasks.append(task)

        elif et == EventType.TASK_CANCELLED:
            tid = payload.get("task_id")
            if tid:
                self._problem.tasks = [t for t in self._problem.tasks if t.id != tid]

        elif et == EventType.TASK_UPDATED:
            tid = payload.get("task_id")
            updates = payload.get("updates") or {}
            if tid and updates:
                self._update_task(tid, updates)

        elif et == EventType.ASSIGNMENT_LOCKED:
            # Locked assignments are recorded; solver fabric may respect them
            # via problem constraints in future extensions.
            pass

        elif et == EventType.HUMAN_OVERRIDE:
            # State already updated in record_decision when applying assignment.
            pass

        elif et == EventType.HORIZON_CHANGED:
            # Horizon updates if provided
            h = payload.get("horizon")
            if h is not None:
                from multiflow.domain.models import TimeHorizon

                self._problem.horizon = TimeHorizon.model_validate(h)

    def _set_resource_availability(self, resource_id: str, *,
 available: bool) -> None:
        for i, r in enumerate(self._problem.resources):
            if r.id == resource_id:
                data = r.model_dump()
                if available:
                    # Restore a full-horizon window if none exist
                    if not data.get("availability"):
                        if self._problem.horizon:
                            data["availability"] = [
                                {
                                    "start": self._problem.horizon.start.isoformat()
                                    if hasattr(self._problem.horizon.start, "isoformat")
                                    else self._problem.horizon.start,
                                    "end": self._problem.horizon.end.isoformat()
                                    if hasattr(self._problem.horizon.end, "isoformat")
                                    else self._problem.horizon.end,
                                }
                            ]
                        else:
                            data["availability"] = []
                else:
                    data["availability"] = []
                self._problem.resources[i] = Resource.model_validate(data)
                return

    def _update_task(self, task_id: str, updates: dict[str, Any]) -> None:
        for t in self._problem.tasks:
            if t.id == task_id:
                data = t.model_dump()
                data.update(updates)
                updated = Task.model_validate(data)
                self._problem.tasks = [
                    updated if x.id == task_id else x for x in self._problem.tasks
                ]
                return
