"""Quantum solver adapter interface.

Does NOT claim quantum hardware execution.
Returns UNAVAILABLE until a quantum companion is configured.

Pipeline (when available):
  SchedulingProblem → quantum encoding → bitstring → CandidateSolution → Validator
"""

from __future__ import annotations

from typing import Any

from multiflow.domain.models import CandidateSolution, SchedulingProblem
from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus


class QuantumSolver(Solver):
    """Interface / seam for a future quantum companion.

    Core package does not depend on a quantum SDK.
    """

    name = "quantum"
    version = "0.0.0-interface"

    def __init__(self, backend_url: str | None = None, **kwargs: Any):
        self.backend_url = backend_url

    def metadata(self) -> dict[str, Any]:
        return {
            "solverId": self.name,
            "solverVersion": self.version,
            "available": False,
            "configuration": {"backend_url": self.backend_url},
            "hint": (
                "Quantum backend is an interface only. "
                "Configure the quantum companion repository against this contract."
            ),
        }

    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        return []

    def solve_result(self, problem: SchedulingProblem) -> SolverResult:
        return SolverResult(
            status=SolverStatus.UNAVAILABLE,
            candidates=[],
            solver_name=self.name,
            solver_version=self.version,
            metadata=self.metadata(),
        )
