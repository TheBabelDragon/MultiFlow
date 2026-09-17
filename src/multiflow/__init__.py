"""MultiFlow – general-purpose scheduling and constraint-arbitration engine.

Public API:

    from multiflow import SchedulingProblem, ClassicalSolver, Validator, get_solver

    problem = SchedulingProblem.from_json("my_problem.json")
    result = get_solver("classical").solve_result(problem)
    for c in result.candidates:
        print(Validator().validate(problem, c).admissible)
"""

from multiflow.domain.models import (
    TimeWindow,
    ResourceType,
    Resource,
    Requirement,
    Task,
    Severity,
    Assignment,
    Schedule,
    ObjectiveDirection,
    Objective,
    SchedulingProblem,
    SolutionScore,
    CandidateSolution,
    ConstraintResult,
    ValidationResult,
    ScheduleConflict,
)
from multiflow.solver.classical import ClassicalSolver
from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus
from multiflow.solver.registry import get_solver, available_solvers
from multiflow.validation.validator import Validator
from multiflow.arbitration.conflicts import ConflictDetector, Arbitrator
from multiflow.constraints.base import Constraint, EvaluationContext
from multiflow.constraints.builtin import (
    NoOverlapConstraint,
    AvailabilityConstraint,
    CapabilityConstraint,
    CapacityConstraint,
    ProtectedWindowConstraint,
    PreferredResourceConstraint,
    TimeWindowConstraint,
)
from multiflow.serialization.io import load_problem, dump_problem

__version__ = "0.1.0"
__schema_prefix__ = "multiflow"

__all__ = [
    "TimeWindow",
    "ResourceType",
    "Resource",
    "Requirement",
    "Task",
    "Severity",
    "Assignment",
    "Schedule",
    "ObjectiveDirection",
    "Objective",
    "SchedulingProblem",
    "SolutionScore",
    "CandidateSolution",
    "ConstraintResult",
    "ValidationResult",
    "ScheduleConflict",
    "ClassicalSolver",
    "Solver",
    "SolverResult",
    "SolverStatus",
    "get_solver",
    "available_solvers",
    "Validator",
    "ConflictDetector",
    "Arbitrator",
    "Constraint",
    "EvaluationContext",
    "NoOverlapConstraint",
    "AvailabilityConstraint",
    "CapabilityConstraint",
    "CapacityConstraint",
    "ProtectedWindowConstraint",
    "PreferredResourceConstraint",
    "TimeWindowConstraint",
    "load_problem",
    "dump_problem",
]
