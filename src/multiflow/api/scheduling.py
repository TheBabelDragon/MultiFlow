"""Versioned scheduling request/response surface for MultiFlow.

Maps to LiveEngine + Validator. Status codes distinguish proposed vs admitted
and preserve NO_COMPLETE_SOLUTION / UNAVAILABLE / INVALID_REQUEST semantics.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from multiflow.domain.models import SchedulingProblem
from multiflow.evidence import DecisionEvidence, OutcomeStatus
from multiflow.live.engine import LiveEngine
from multiflow.solver.classical import ClassicalSolver
from multiflow.solver.interface import Solver
from multiflow.validation.validator import Validator

API_SCHEMA_ID = "multiflow.scheduling_api"
API_SCHEMA_VERSION = "1.0.0"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SchedulingStatus(str, Enum):
    """Result status for a scheduling API call.

    Maps onto existing OutcomeStatus / solver outcomes without replacing them.
    """

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    NO_COMPLETE_SOLUTION = "NO_COMPLETE_SOLUTION"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID_REQUEST = "INVALID_REQUEST"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"
    SOLVER_ERROR = "SOLVER_ERROR"
    PROPOSED = "PROPOSED"  # candidates exist but none admitted yet


class HealthStatus(BaseModel):
    schema_id: str = API_SCHEMA_ID
    schema_version: str = API_SCHEMA_VERSION
    healthy: bool = True
    solver_name: str = "ClassicalSolver"
    solver_available: bool = True
    validator_available: bool = True
    python_requires: str = ">=3.11"
    capabilities: list[str] = Field(
        default_factory=lambda: [
            "classical_solver",
            "independent_validator",
            "decision_evidence",
            "no_complete_solution",
            "idempotent_requests",
        ]
    )
    detail: str = ""


class SchedulingRequest(BaseModel):
    """Versioned scheduling request.

    correlation_id enables idempotent retries. problem is the normalized
    SchedulingProblem (or dict accepted by model_validate).
    """

    schema_id: str = API_SCHEMA_ID
    schema_version: str = API_SCHEMA_VERSION
    request_id: str = Field(default_factory=lambda: _new_id("req"))
    correlation_id: str = Field(default_factory=lambda: _new_id("corr"))
    problem: dict[str, Any] = Field(default_factory=dict)
    preferences: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    snapshot_version: Optional[str] = None
    expected_snapshot_version: Optional[str] = None  # stale check
    timeout_seconds: Optional[float] = None
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _major_compat(cls, v: str) -> str:
        major = (v or "0").split(".")[0]
        if major != API_SCHEMA_VERSION.split(".")[0]:
            raise ValueError(
                f"incompatible major schema version {v!r}; need {API_SCHEMA_VERSION}"
            )
        return v


class SchedulingResponse(BaseModel):
    schema_id: str = API_SCHEMA_ID
    schema_version: str = API_SCHEMA_VERSION
    request_id: str = ""
    correlation_id: str = ""
    status: SchedulingStatus = SchedulingStatus.UNAVAILABLE
    snapshot_id: str = ""
    snapshot_version: Optional[str] = None
    proposed_candidates: list[dict[str, Any]] = Field(default_factory=list)
    admitted_plan: Optional[dict[str, Any]] = None
    rejected_candidates: dict[str, str] = Field(default_factory=dict)
    blocking_reasons: list[str] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[dict[str, Any]] = None
    solver_identity: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SchedulingApi:
    """In-process versioned scheduling façade over LiveEngine."""

    def __init__(
        self,
        *,
        solver: Optional[Solver] = None,
        validator: Optional[Validator] = None,
    ) -> None:
        self._solver = solver or ClassicalSolver()
        self._validator = validator or Validator()
        self._engines: dict[str, LiveEngine] = {}
        self._responses: dict[str, SchedulingResponse] = {}  # correlation_id → last

    def health(self) -> HealthStatus:
        return HealthStatus(
            solver_name=type(self._solver).__name__,
            solver_available=True,
            validator_available=True,
        )

    def negotiate(self, client_schema_version: str) -> dict[str, Any]:
        try:
            major = client_schema_version.split(".")[0]
            ok = major == API_SCHEMA_VERSION.split(".")[0]
        except Exception:
            ok = False
        return {
            "compatible": ok,
            "server_schema_id": API_SCHEMA_ID,
            "server_schema_version": API_SCHEMA_VERSION,
            "client_schema_version": client_schema_version,
        }

    def schedule(self, request: SchedulingRequest | dict[str, Any]) -> SchedulingResponse:
        t0 = time.perf_counter()
        try:
            if isinstance(request, dict):
                request = SchedulingRequest.model_validate(request)
        except Exception as e:
            return SchedulingResponse(
                status=SchedulingStatus.INVALID_REQUEST,
                error=str(e),
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )

        # Idempotent: same correlation_id returns prior response
        if request.correlation_id in self._responses:
            prior = self._responses[request.correlation_id]
            return prior.model_copy(
                update={"attributes": {**prior.attributes, "idempotent_replay": True}}
            )

        if request.expected_snapshot_version and request.snapshot_version:
            if request.expected_snapshot_version != request.snapshot_version:
                resp = SchedulingResponse(
                    request_id=request.request_id,
                    correlation_id=request.correlation_id,
                    status=SchedulingStatus.STALE_SNAPSHOT,
                    snapshot_version=request.snapshot_version,
                    error="snapshot_version does not match expected_snapshot_version",
                    duration_ms=round((time.perf_counter() - t0) * 1000, 2),
                )
                self._responses[request.correlation_id] = resp
                return resp

        if not request.problem:
            resp = SchedulingResponse(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status=SchedulingStatus.INVALID_REQUEST,
                error="problem is required",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
            self._responses[request.correlation_id] = resp
            return resp

        try:
            problem = SchedulingProblem.model_validate(request.problem)
        except Exception as e:
            resp = SchedulingResponse(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status=SchedulingStatus.INVALID_REQUEST,
                error=f"invalid problem: {e}",
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
            self._responses[request.correlation_id] = resp
            return resp

        if request.preferences:
            attrs = dict(problem.attributes or {})
            attrs["policy_preferences"] = request.preferences
            problem = problem.model_copy(update={"attributes": attrs})

        try:
            engine = LiveEngine(
                initial_problem=problem,
                solver=self._solver,
                validator=self._validator,
            )
            result = engine.recalculate()
        except Exception as e:
            resp = SchedulingResponse(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status=SchedulingStatus.SOLVER_ERROR,
                error=str(e),
                solver_identity=type(self._solver).__name__,
                duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            )
            self._responses[request.correlation_id] = resp
            return resp

        admissible = result.get("admissible") or result.get("admissible_candidates") or []
        rejected = result.get("rejected") or {}
        if not isinstance(rejected, dict):
            rejected = {}

        proposed: list[dict[str, Any]] = []
        admitted_plan: Optional[dict[str, Any]] = None
        for i, cand in enumerate(admissible):
            d = cand.model_dump() if hasattr(cand, "model_dump") else dict(cand) if isinstance(cand, dict) else {"raw": str(cand)}
            proposed.append(d)
            if i == 0:
                admitted_plan = d

        evidence_dict = None
        if engine.evidence_history:
            evidence_dict = engine.evidence_history[-1].model_dump(mode="json")

        if admitted_plan:
            status = SchedulingStatus.ADMITTED
        elif proposed:
            status = SchedulingStatus.PROPOSED
        else:
            status = SchedulingStatus.NO_COMPLETE_SOLUTION

        blocking = []
        if status == SchedulingStatus.NO_COMPLETE_SOLUTION:
            blocking = list(rejected.values()) if rejected else ["NO_COMPLETE_SOLUTION"]

        snap_id = ""
        if engine._last_snapshot is not None:
            snap_id = getattr(engine._last_snapshot, "id", "") or ""

        resp = SchedulingResponse(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status=status,
            snapshot_id=str(snap_id),
            snapshot_version=request.snapshot_version,
            proposed_candidates=proposed,
            admitted_plan=admitted_plan,
            rejected_candidates={str(k): str(v) for k, v in rejected.items()},
            blocking_reasons=blocking,
            validation_summary=dict(result.get("validation") or {}) if isinstance(result.get("validation"), dict) else {},
            evidence=evidence_dict,
            solver_identity=type(self._solver).__name__,
            duration_ms=round((time.perf_counter() - t0) * 1000, 2),
            attributes={"evidence_refs": request.evidence_refs},
        )
        self._responses[request.correlation_id] = resp
        return resp

    def get_evidence(self, correlation_id: str) -> Optional[dict[str, Any]]:
        resp = self._responses.get(correlation_id)
        if not resp:
            return None
        return resp.evidence
