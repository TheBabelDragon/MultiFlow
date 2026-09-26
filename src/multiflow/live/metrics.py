"""Domain-neutral operational metrics for the live engine."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OperationalMetrics(BaseModel):
    """Deterministic, testable counters — no external telemetry dependency."""

    schema_version: str = "multiflow.metrics.v1"
    events_processed: int = 0
    recalculations: int = 0
    candidates_generated: int = 0
    admissible_candidates: int = 0
    rejected_candidates: int = 0
    solver_runtime_seconds: float = 0.0
    validation_runtime_seconds: float = 0.0
    decisions: int = 0
    overrides: int = 0
    infeasible_recalculations: int = 0
    attributes: dict[str, Any] = Field(default_factory=dict)

    def record_event(self) -> None:
        self.events_processed += 1

    def record_recalculation(
        self,
        candidates: int,
        admissible: int,
        rejected: int,
        solver_runtime: float = 0.0,
        validation_runtime: float = 0.0,
        infeasible: bool = False,
    ) -> None:
        self.recalculations += 1
        self.candidates_generated += candidates
        self.admissible_candidates += admissible
        self.rejected_candidates += rejected
        self.solver_runtime_seconds += solver_runtime
        self.validation_runtime_seconds += validation_runtime
        if infeasible:
            self.infeasible_recalculations += 1

    def record_decision(self, is_override: bool = False) -> None:
        self.decisions += 1
        if is_override:
            self.overrides += 1

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def reset(self) -> None:
        self.events_processed = 0
        self.recalculations = 0
        self.candidates_generated = 0
        self.admissible_candidates = 0
        self.rejected_candidates = 0
        self.solver_runtime_seconds = 0.0
        self.validation_runtime_seconds = 0.0
        self.decisions = 0
        self.overrides = 0
        self.infeasible_recalculations = 0
        self.attributes = {}
