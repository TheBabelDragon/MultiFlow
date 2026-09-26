"""Decision recording for solver selections and human overrides."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionSource(str, Enum):
    SOLVER = "solver"
    HUMAN_OVERRIDE = "human_override"
    DETERMINISTIC_SCORER = "deterministic_scorer"
    SYSTEM = "system"


class DecisionRecord(BaseModel):
    """Record of a decision taken after ranking admissible candidates.

    Human overrides ADD information; they never erase the original solver
    decision. Both can coexist in the decision history.
    """

    schema_version: str = "multiflow.decision.v1"
    id: str = Field(default_factory=lambda: _new_id("dec"))
    snapshot_id: str
    selected_candidate_id: Optional[str] = None
    source: DecisionSource = DecisionSource.SOLVER
    timestamp: datetime = Field(default_factory=_utc_now)
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    human_override: bool = False
    override_reason: str = ""
    override_of_decision_id: Optional[str] = None
    resulting_event_id: Optional[str] = None
    outcome: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    admissible_candidate_ids: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
