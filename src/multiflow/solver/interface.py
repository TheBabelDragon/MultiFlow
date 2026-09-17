"""Solver fabric interface.

Solver
 ├── solve(SchedulingProblem) -> list[CandidateSolution]
 ├── solve_result(SchedulingProblem) -> SolverResult
 └── metadata()

Implementations may be Classical, MILP, CP-SAT, Quantum.
The domain model never changes. Solvers only propose.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from multiflow.domain.models import CandidateSolution, SchedulingProblem
from multiflow.solver.result import SolverResult, SolverStatus


class Solver(ABC):
    """Abstract solver backend."""

    name: str = "abstract"
    version: str = "0.0.0"

    @abstractmethod
    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        """Return zero or more candidate solutions. Never claims correctness."""
        ...

    def solve_result(self, problem: SchedulingProblem) -> SolverResult:
        """Return a structured SolverResult wrapping candidates.

        Default implementation wraps solve(). Backends may override for
        richer status (OPTIMAL / INFEASIBLE / TIME_LIMIT / UNAVAILABLE).
        """
        import time

        t0 = time.perf_counter()
        try:
            candidates = self.solve(problem)
        except Exception as exc:  # noqa: BLE001
            return SolverResult(
                status=SolverStatus.ERROR,
                candidates=[],
                solver_name=getattr(self, "name", "unknown"),
                solver_version=getattr(self, "version", "0.0.0"),
                runtime_seconds=time.perf_counter() - t0,
                metadata={"error": str(exc)},
            )
        runtime = time.perf_counter() - t0
        if not candidates:
            status = SolverStatus.INFEASIBLE
        else:
            status = SolverStatus.FEASIBLE
        return SolverResult(
            status=status,
            candidates=candidates,
            solver_name=getattr(self, "name", "unknown"),
            solver_version=getattr(self, "version", "0.0.0"),
            runtime_seconds=runtime,
            metadata=self.metadata(),
        )

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """solverId, solverVersion, configuration, etc."""
        ...
