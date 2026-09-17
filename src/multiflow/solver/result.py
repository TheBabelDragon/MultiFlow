"""Solver result types.

Solvers report status and candidates. The Independent Validator decides
whether any candidate is admissible. Solver status is descriptive only.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from multiflow.domain.models import CandidateSolution


class SolverStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    TIME_LIMIT = "TIME_LIMIT"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"


class SolverResult(BaseModel):
    """Outcome of a solver backend.

    status describes what the solver believes about the search.
    It does NOT establish MultiFlow validity — the Validator does.
    """

    status: SolverStatus
    candidates: list[CandidateSolution] = Field(default_factory=list)
    solver_name: str
    solver_version: str
    objective_value: Optional[float] = None
    runtime_seconds: Optional[float] = None
    termination_reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.status != SolverStatus.UNAVAILABLE
