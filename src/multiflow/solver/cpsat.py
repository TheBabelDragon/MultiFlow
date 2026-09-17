"""CP-SAT backend via OR-Tools (optional).

Install: pip install "multiflow[cp-sat]"

Pipeline:
  SchedulingProblem -> CP-SAT model -> solution -> CandidateSolution -> Validator
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from multiflow.domain.models import (
    Assignment,
    CandidateSolution,
    SchedulingProblem,
    SolutionScore,
    TimeWindow,
)
from multiflow.solver.interface import Solver
from multiflow.solver.result import SolverResult, SolverStatus


def _require_ortools():
    try:
        from ortools.sat.python import cp_model  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            'OR-Tools is required for the CP-SAT backend. '
            'Install with: pip install "multiflow[cp-sat]"'
        ) from exp


class CPSATSolver(Solver):
    name = "cp-sat"
    version = "0.1.0"

    def __init__(self, time_limit_seconds: float = 10.0, max_candidates: int = 3):
        _require_ortools()
        self.time_limit_seconds = time_limit_seconds
        self.max_candidates = max_candidates

    def metadata(self) -> dict[str, Any]:
        return {
            "solverId": self.name,
            "solverVersion": self.version,
            "configuration": {
                "time_limit_seconds": self.time_limit_seconds,
                "max_candidates": self.max_candidates,
            },
        }

    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        return self.solve_result(problem).candidates

    def solve_result(self, problem: SchedulingProblem) -> SolverResult:
        from ortools.sat.python import cp_model

        t0 = time.perf_counter()
        model = cp_model.CpModel()

        all_starts = []
        all_ends = []
        for t in problem.tasks:
            for w in t.allowed_windows:
                all_starts.append(w.start)
                all_ends.append(w.end)
        for r in problem.resources:
            for w in r.availability:
                all_starts.append(w.start)
                all_ends.append(w.end)
        if not all_starts:
            return SolverResult(
                status=SolverStatus.INFEASIBLE,
                candidates=[],
                solver_name=self.name,
                solver_version=self.version,
                runtime_seconds=time.perf_counter() - t0,
            )

        origin = min(all_starts)
        horizon = int((max(all_ends) - origin).total_seconds() // 60) + 1

        def to_min(dt: datetime) -> int:
            return int((dt - origin).total_seconds() // 60)

        task_starts: dict[str, Any] = {}
        task_presences: dict[str, dict[str, Any]] = {}

        for task in problem.tasks:
            duration_m = max(1, int(task.duration.total_seconds() // 60))
            if task.allowed_windows:
                lo = min(to_min(w.start) for w in task.allowed_windows)
                hi = max(to_min(w.end) for w in task.allowed_windows) - duration_m
            else:
                lo, hi = 0, horizon - duration_m
            hi = max(lo, hi)
            start_var = model.NewIntVar(lo, hi, f"start_{task.id}")
            end_var = model.NewIntVar(lo + duration_m, hi + duration_m, f"end_{task.id}")
            task_starts[task.id] = start_var
            task_presences[task.id] = {}

            candidates = []
            for res in problem.resources:
                matches = False
                for req in task.requirements:
                    if req.resource_ids and res.id in req.resource_ids:
                        matches = True
                    if req.capability and req.capability in res.capabilities:
                        matches = True
                if not matches and not task.requirements:
                    matches = True
                if not matches:
                    continue
                present = model.NewBoolVar(f"pres_{task.id}_{res.id}")
                task_presences[task.id][res.id] = present
                candidates.append(present)
                opt_iv = model.NewOptionalIntervalVar(
                    start_var, duration_m, end_var, present, f"opt_{task.id}_{res.id}"
                )
                setattr(model, f"_opt_{task.id}_{res.id}", opt_iv)

            if candidates:
                model.Add(sum(candidates) >= 1)

        for res in problem.resources:
            intervals = []
            for task in problem.tasks:
                if res.id in task_presences.get(task.id, {}):
                    intervals.append(getattr(model, f"_opt_{task.id}_{res.id}"))
            if len(intervals) >= 2:
                model.AddNoOverlap(intervals)

        model.Minimize(sum(task_starts[t.id] for t in problem.tasks))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        status_code = solver.Solve(model)
        runtime = time.perf_counter() - t0

        status_map = {
            cp_model.OPTIMAL: SolverStatus.OPTIMAL,
            cp_model.FEASIBLE: SolverStatus.FEASIBLE,
            cp_model.INFEASIBLE: SolverStatus.INFEASIBLE,
            cp_model.MODEL_INVALID: SolverStatus.ERROR,
            cp_model.UNKNOWN: SolverStatus.TIME_LIMIT,
        }
        status = status_map.get(status_code, SolverStatus.ERROR)

        candidates_out: list[CandidateSolution] = []
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            assignments = []
            for task in problem.tasks:
                start_m = solver.Value(task_starts[task.id])
                duration_m = max(1, int(task.duration.total_seconds() // 60))
                start_dt = origin + timedelta(minutes=start_m)
                end_dt = start_dt + timedelta(minutes=duration_m)
                res_ids = [
                    rid for rid, var in task_presences[task.id].items()
                    if solver.Value(var) == 1
                ]
                assignments.append(
                    Assignment(
                        task_id=task.id,
                        resource_ids=res_ids,
                        window=TimeWindow(start=start_dt, end=end_dt),
                        schedule_id=task.schedule_id,
                    )
                )
            candidates_out.append(
                CandidateSolution(
                    id=f"cand-cpsat-{uuid.uuid4().hex[:12]}",
                    problem_id=problem.id,
                    assignments=assignments,
                    solver_id=self.name,
                    solver_version=self.version,
                    score=SolutionScore(),
                )
            )

        return SolverResult(
            status=status,
            candidates=candidates_out,
            solver_name=self.name,
            solver_version=self.version,
            objective_value=solver.ObjectiveValue() if candidates_out else None,
            runtime_seconds=runtime,
            metadata={**self.metadata(), "ortools_status": solver.StatusName(status_code)},
        )
