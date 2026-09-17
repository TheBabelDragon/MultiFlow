"""MILP backend via PuLP + CBC (optional).

Install: pip install "multiflow[milp]"

Pipeline:
  SchedulingProblem -> MILP -> CandidateSolution -> Validator
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


def _require_pulp():
    try:
        import pulp  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            'PuLP is required for the MILP backend. '
            'Install with: pip install "multiflow[milp]"'
        ) from exc


class MILPSolver(Solver):
    name = "milp"
    version = "0.1.0"

    def __init__(self, time_limit_seconds: float = 10.0, max_candidates: int = 1):
        _require_pulp()
        self.time_limit_seconds = time_limit_seconds
        self.max_candidates = max_candidates

    def metadata(self) -> dict[str, Any]:
        return {
            "solverId": self.name,
            "solverVersion": self.version,
            "configuration": {"time_limit_seconds": self.time_limit_seconds},
        }

    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        return self.solve_result(problem).candidates

    def solve_result(self, problem: SchedulingProblem) -> SolverResult:
        import pulp

        t0 = time.perf_counter()

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
        step = 15
        horizon_m = int((max(all_ends) - origin).total_seconds() // 60)
        slots = list(range(0, horizon_m + 1, step))

        def to_slot(dt: datetime) -> int:
            return int((dt - origin).total_seconds() // 60)

        prob = pulp.LpProblem("multiflow_milp", pulp.LpMinimize)
        x = {}

        for task in problem.tasks:
            duration_m = max(step, int(task.duration.total_seconds() // 60))
            allowed = []
            for w in task.allowed_windows:
                lo = to_slot(w.start)
                hi = to_slot(w.end) - duration_m
                for s in slots:
                    if lo <= s <= hi:
                        allowed.append(s)
            if not allowed:
                allowed = [s for s in slots if s + duration_m <= horizon_m]

            matching_resources = []
            for res in problem.resources:
                matches = False
                for req in task.requirements:
                    if req.resource_ids and res.id in req.resource_ids:
                        matches = True
                    if req.capability and req.capability in res.capabilities:
                        matches = True
                if not task.requirements:
                    matches = True
                if matches:
                    matching_resources.append(res)

            for res in matching_resources:
                for s in allowed:
                    var = pulp.LpVariable(
                        f"x_{task.id}_{res.id}_{s}", cat=pulp.LpBinary
                    )
                    x[(task.id, res.id, s)] = var

            task_vars = [v for (tid, _, _), v in x.items() if tid == task.id]
            if task_vars:
                prob += pulp.lpSum(task_vars) == 1, f"assign_{task.id}"

        for res in problem.resources:
            for s in slots:
                covering = []
                for (tid, rid, start), var in x.items():
                    if rid != res.id:
                        continue
                    task = next(t for t in problem.tasks if t.id == tid)
                    duration_m = max(step, int(task.duration.total_seconds() // 60))
                    if start <= s < start + duration_m:
                        covering.append(var)
                if covering:
                    prob += pulp.lpSum(covering) <= 1, f"cap_{res.id}_{s}"

        prob += pulp.lpSum(start * var for (_, _, start), var in x.items()), "earlier_better"

        solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=self.time_limit_seconds)
        try:
            highs = pulp.HiGHS_CMD(msg=False, timeLimit=self.time_limit_seconds)
            if highs.available():
                solver = highs
        except Exception:
            pass

        status_code = prob.solve(solver)
        runtime = time.perf_counter() - t0

        pulp_status = pulp.LpStatus.get(status_code, "Unknown")
        if pulp_status == "Optimal":
            status = SolverStatus.OPTIMAL
        elif pulp_status in ("Feasible", "Not Solved"):
            if any(pulp.value(v) and pulp.value(v) > 0.5 for v in x.values()):
                status = SolverStatus.FEASIBLE
            else:
                status = SolverStatus.TIME_LIMIT
        elif pulp_status == "Infeasible":
            status = SolverStatus.INFEASIBLE
        else:
            status = SolverStatus.ERROR

        candidates: list[CandidateSolution] = []
        if status in (SolverStatus.OPTIMAL, SolverStatus.FEASIBLE):
            chosen: dict[str, list] = {}
            for (tid, rid, start), var in x.items():
                val = pulp.value(var)
                if val is not None and val > 0.5:
                    chosen.setdefault(tid, []).append((rid, start))

            assignments = []
            for task in problem.tasks:
                picks = chosen.get(task.id, [])
                if not picks:
                    continue
                res_ids = [rid for rid, _ in picks]
                start_m = min(s for _, s in picks)
                duration_m = max(step, int(task.duration.total_seconds() // 60))
                start_dt = origin + timedelta(minutes=start_m)
                end_dt = start_dt + timedelta(minutes=duration_m)
                assignments.append(
                    Assignment(
                        task_id=task.id,
                        resource_ids=res_ids,
                        window=TimeWindow(start=start_dt, end=end_dt),
                        schedule_id=task.schedule_id,
                    )
                )
            if assignments:
                candidates.append(
                    CandidateSolution(
                        id=f"cand-milp-{uuid.uuid4().hex[:12]}",
                        problem_id=problem.id,
                        assignments=assignments,
                        solver_id=self.name,
                        solver_version=self.version,
                        score=SolutionScore(),
                    )
                )

        return SolverResult(
            status=status,
            candidates=candidates,
            solver_name=self.name,
            solver_version=self.version,
            objective_value=pulp.value(prob.objective) if candidates else None,
            runtime_seconds=runtime,
            metadata={**self.metadata(), "pulp_status": pulp_status},
        )
