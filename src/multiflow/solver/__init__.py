"""Solver fabric: classical / cp-sat / milp / quantum."""

from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus
from multiflow.solver.classical import ClassicalSolver
from multiflow.solver.registry import available_solvers, get_solver

__all__ = [
    "Solver",
    "SolverResult",
    "SolverStatus",
    "ClassicalSolver",
    "get_solver",
    "available_solvers",
]
