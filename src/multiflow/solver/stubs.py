"""Unavailable solver stubs for optional backends without dependencies."""

from __future__ import annotations

from typing import Any

from multiflow.domain.models import CandidateSolution, SchedulingProblem
from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus


class UnavailableSolver(Solver):
    """Raises on construction or returns UNAVAILABLE on solve_result."""

    name = "unavailable"
    version = "0.0.0"
    install_hint = ""

    def __init__(self, **kwargs: Any):
        raise ImportError(
            f"Solver '{self.name}' is unavailable. {self.install_hint}"
        )

    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        return []

    def solve_result(self, problem: SchedulingProblem) -> SolverResult:
        return SolverResult(
            status=SolverStatus.UNAVAILABLE,
            candidates=[],
            solver_name=self.name,
            solver_version=self.version,
            metadata={"hint": self.install_hint},
        )

    def metadata(self) -> dict[str, Any]:
        return {
            "solverId": self.name,
            "solverVersion": self.version,
            "available": False,
            "hint": self.install_hint,
        }
