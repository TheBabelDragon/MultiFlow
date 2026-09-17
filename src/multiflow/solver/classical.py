"""Deterministic classical greedy scheduler for MVP."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Optional

from multiflow.domain.models import (
    Assignment,
    CandidateSolution,
    Resource,
    SchedulingProblem,
    SolutionScore,
    Task,
    TimeWindow,
)
from multiflow.solver.interface import Solver
from multiflow.validation.validator import Validator


class ClassicalSolver(Solver):
    name = "classical"
    version = "0.2.0"
    SOLVER_ID = "classical-greedy"
    VERSION = "0.2.0"

    def __init__(
        self,
        max_candidates: int = 5,
        seed: int = 0,
        slide_step: Optional[timedelta] = None,
        min_separation: Optional[timedelta] = None,
    ):
        self.max_candidates = max_candidates
        self.seed = seed
        self.slide_step = slide_step or timedelta(minutes=15)
        self.min_separation = min_separation or timedelta(minutes=15)
        self.validator = Validator()

    def metadata(self) -> dict[str, Any]:
        return {
            "solverId": self.SOLVER_ID,
            "solverVersion": self.VERSION,
            "configuration": {
                "max_candidates": self.max_candidates,
                "seed": self.seed,
                "slide_step_seconds": self.slide_step.total_seconds(),
                "min_separation_seconds": self.min_separation.total_seconds(),
            },
        }

    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]:
        resources = {r.id: r for r in problem.resources}
        base = list(problem.existing_assignments)

        orderings = [
            sorted(problem.tasks, key=lambda t: (-t.priority, -t.duration.total_seconds(), t.id)),
            sorted(problem.tasks, key=lambda t: (t.priority, t.duration.total_seconds(), t.id)),
            sorted(problem.tasks, key=lambda t: t.id),
        ]

        candidates: list[CandidateSolution] = []
        seen: set[tuple] = set()

        for oi, tasks in enumerate(orderings):
            for offset in range(min(3, max(1, len(resources)))):
                assignments = list(base)
                used: dict[str, list[TimeWindow]] = {}
                for a in base:
                    for rid in a.resource_ids:
                        used.setdefault(rid, []).append(a.window)

                for task in tasks:
                    placed = self._place(task, resources, used, offset)
                    if placed is None:
                        continue
                    res_ids, window = placed
                    assignments.append(
                        Assignment(
                            task_id=task.id,
                            resource_ids=res_ids,
                            window=window,
                            schedule_id=task.schedule_id,
                        )
                    )
                    for rid in res_ids:
                        used.setdefault(rid, []).append(window)

                key = tuple(
                    sorted(
                        (a.task_id, tuple(a.resource_ids), a.window.start.isoformat(), a.window.end.isoformat())
                        for a in assignments
                    )
                )
                if key in seen:
                    continue
                seen.add(key)

                cand = CandidateSolution(
                    problem_id=problem.id,
                    assignments=assignments,
                    solver_id=self.SOLVER_ID,
                    solver_version=self.VERSION,
                    score=SolutionScore(),
                )
                vr = self.validator.validate(problem, cand)
                cand.score = vr.score
                candidates.append(cand)
                if len(candidates) >= self.max_candidates:
                    break
            if len(candidates) >= self.max_candidates:
                break

        candidates.sort(key=lambda c: (not c.score.admissible, c.score.soft_penalty, -len(c.assignments)))
        return candidates[: self.max_candidates]

    def _place(self, task, resources, used, resource_offset):
        windows = list(task.allowed_windows) or []
        if not windows:
            return None
        windows = sorted(windows, key=lambda w: w.start)
        for aw in windows:
            start = aw.start
            while start + task.duration <= aw.end:
                slot = TimeWindow(start=start, end=start + task.duration)
                res_ids = self._pick_resources(task, resources, used, slot, resource_offset)
                if res_ids is not None:
                    return res_ids, slot
                start = start + self.slide_step
        return None

    def _pick_resources(self, task, resources, used, slot, resource_offset):
        if not task.requirements:
            candidates = sorted(resources.values(), key=lambda r: r.id)
            if resource_offset:
                candidates = candidates[resource_offset:] + candidates[:resource_offset]
            for res in candidates:
                if self._is_free(res, slot, used):
                    return [res.id]
            return None

        chosen = []
        reserved = set()
        for req in task.requirements:
            qty = max(1, req.quantity)
            matches = self._matching_resources(req, resources)
            if resource_offset:
                matches = matches[resource_offset:] + matches[:resource_offset]
            picked = 0
            for res in matches:
                if res.id in reserved:
                    continue
                if not self._is_free(res, slot, used):
                    continue
                chosen.append(res.id)
                reserved.add(res.id)
                picked += 1
                if picked >= qty:
                    break
            if picked < qty:
                return None
        return chosen

    def _matching_resources(self, req, resources):
        out = []
        for r in resources.values():
            if req.resource_ids and r.id not in req.resource_ids:
                continue
            if req.resource_type and r.type != req.resource_type:
                continue
            if req.capability and req.capability not in r.capabilities:
                continue
            out.append(r)
        out.sort(key=lambda r: r.id)
        return out

    def _is_free(self, res, slot, used):
        if not res.is_available_during(slot):
            return False
        for w in used.get(res.id, []):
            if w.overlaps(slot):
                return False
            if slot.start >= w.end and slot.start - w.end < self.min_separation:
                return False
            if w.start >= slot.end and w.start - slot.end < self.min_separation:
                return False
        return True
