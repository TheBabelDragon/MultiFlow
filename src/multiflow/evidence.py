"""Shared Evidence Contract — MultiFlow decision and outcome records.

Captures decision inputs, constraint versions, chosen action, rejected
alternatives, and outcome identity. Solver proposals stay separate from
admitted results. Overrides add information; they never erase history.

Does not import CANtheon, MetaField, or TensorGate. Upstream links are
plain evidence_refs dicts.
"""

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


class OutcomeStatus(str, Enum):
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    OVERRIDE = "OVERRIDE"
    NO_SOLUTION = "NO_SOLUTION"
    PROPOSED = "PROPOSED"


class ConstraintVersion(BaseModel):
    """Identity of a constraint set used at decision time."""

    constraint_id: str = ""
    version: str = ""
    schema_id: str = "multiflow.constraint"
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class DecisionEvidence(BaseModel):
    """Evidence envelope for one MultiFlow decision boundary crossing."""

    schema_id: str = "multiflow.decision_evidence"
    schema_version: str = "0.1.0"
    decision_id: str = Field(default_factory=lambda: _new_id("dec"))
    snapshot_id: str = ""
    proposed_candidate_ids: list[str] = Field(default_factory=list)
    admitted_candidate_id: Optional[str] = None
    rejected_candidate_ids: list[str] = Field(default_factory=list)
    rejection_reasons: dict[str, str] = Field(default_factory=dict)
    constraint_versions: list[ConstraintVersion] = Field(default_factory=list)
    outcome_status: OutcomeStatus = OutcomeStatus.PROPOSED
    outcome_id: str = Field(default_factory=lambda: _new_id("out"))
    outcome_attributes: dict[str, Any] = Field(default_factory=dict)
    human_override: bool = False
    override_reason: str = ""
    override_of_decision_id: Optional[str] = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    solver_id: str = ""
    solver_version: str = ""
    source: str = "solver"
    timestamp: datetime = Field(default_factory=_utc_now)
    extras: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DecisionEvidence":
        return cls.model_validate(data)


def build_decision_evidence(
    *,
    snapshot_id: str,
    proposed_candidate_ids: Optional[list[str]] = None,
    admitted_candidate_id: Optional[str] = None,
    rejected_candidate_ids: Optional[list[str]] = None,
    rejection_reasons: Optional[dict[str, str]] = None,
    constraint_versions: Optional[list[ConstraintVersion]] = None,
    outcome_status: OutcomeStatus = OutcomeStatus.PROPOSED,
    human_override: bool = False,
    override_reason: str = "",
    override_of_decision_id: Optional[str] = None,
    evidence_refs: Optional[list[dict[str, Any]]] = None,
    solver_id: str = "",
    solver_version: str = "",
    source: str = "solver",
    outcome_attributes: Optional[dict[str, Any]] = None,
) -> DecisionEvidence:
    """Construct DecisionEvidence with fail-closed checks."""
    if outcome_status == OutcomeStatus.ADMITTED and not admitted_candidate_id:
        raise ValueError("ADMITTED outcome requires admitted_candidate_id")
    if outcome_status == OutcomeStatus.OVERRIDE and not human_override:
        human_override = True

    return DecisionEvidence(
        snapshot_id=snapshot_id,
        proposed_candidate_ids=list(proposed_candidate_ids or []),
        admitted_candidate_id=admitted_candidate_id,
        rejected_candidate_ids=list(rejected_candidate_ids or []),
        rejection_reasons=dict(rejection_reasons or {}),
        constraint_versions=list(constraint_versions or []),
        outcome_status=outcome_status,
        human_override=human_override,
        override_reason=override_reason,
        override_of_decision_id=override_of_decision_id,
        evidence_refs=list(evidence_refs or []),
        solver_id=solver_id,
        solver_version=solver_version,
        source=source,
        outcome_attributes=dict(outcome_attributes or {}),
    )


def attach_evidence_ref(
    evidence: DecisionEvidence,
    *,
    event_id: str = "",
    source_id: str = "",
    schema_id: str = "",
    schema_version: str = "",
    extras: Optional[dict[str, Any]] = None,
) -> DecisionEvidence:
    """Append an upstream evidence reference."""
    ref: dict[str, Any] = {}
    if event_id:
        ref["event_id"] = event_id
    if source_id:
        ref["source_id"] = source_id
    if schema_id:
        ref["schema_id"] = schema_id
    if schema_version:
        ref["schema_version"] = schema_version
    if extras:
        ref["extras"] = dict(extras)
    if ref:
        refs = list(evidence.evidence_refs) + [ref]
        return evidence.model_copy(update={"evidence_refs": refs})
    return evidence


def check_evidence_schema(
    evidence: DecisionEvidence,
    *,
    expected_schema_id: str = "multiflow.decision_evidence",
    expected_major: int = 0,
) -> None:
    """Fail-closed schema major version check."""
    if evidence.schema_id and evidence.schema_id != expected_schema_id:
        raise ValueError(
            f"incompatible evidence schema_id: {evidence.schema_id!r} "
            f"(expected {expected_schema_id!r})"
        )
    try:
        major = int(str(evidence.schema_version).split(".")[0])
    except ValueError as exc:
        raise ValueError(
            f"unparseable evidence schema_version: {evidence.schema_version!r}"
        ) from exc
    if major != expected_major:
        raise ValueError(
            f"incompatible evidence major version: {evidence.schema_version} "
            f"(supported major={expected_major})"
        )


def decision_record_to_evidence(
    record: Any,
    *,
    constraint_versions: Optional[list[ConstraintVersion]] = None,
    solver_id: str = "",
    solver_version: str = "",
    evidence_refs: Optional[list[dict[str, Any]]] = None,
) -> DecisionEvidence:
    """Map an existing DecisionRecord into DecisionEvidence."""
    admitted = getattr(record, "selected_candidate_id", None)
    rejected = list(getattr(record, "rejected_candidate_ids", None) or [])
    reasons = dict(getattr(record, "rejection_reasons", None) or {})
    admissible = list(getattr(record, "admissible_candidate_ids", None) or [])
    human = bool(getattr(record, "human_override", False))

    if human:
        status = OutcomeStatus.OVERRIDE
    elif admitted:
        status = OutcomeStatus.ADMITTED
    elif not admissible and not admitted:
        status = OutcomeStatus.NO_SOLUTION
    else:
        status = OutcomeStatus.PROPOSED

    return build_decision_evidence(
        snapshot_id=str(getattr(record, "snapshot_id", "") or ""),
        proposed_candidate_ids=admissible,
        admitted_candidate_id=admitted,
        rejected_candidate_ids=rejected,
        rejection_reasons=reasons,
        constraint_versions=constraint_versions,
        outcome_status=status,
        human_override=human,
        override_reason=str(getattr(record, "override_reason", "") or ""),
        override_of_decision_id=getattr(record, "override_of_decision_id", None),
        evidence_refs=evidence_refs,
        solver_id=solver_id,
        solver_version=solver_version,
        source=str(
            getattr(getattr(record, "source", None), "value", None)
            or getattr(record, "source", "solver")
        ),
        outcome_attributes=dict(getattr(record, "outcome", None) or {}),
    )
