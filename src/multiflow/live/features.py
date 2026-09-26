"""Stable feature boundary for future learned ranking.

Features are explicit, serializable, deterministic data — not raw domain graphs.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from multiflow.domain.models import CandidateSolution, SchedulingProblem
from multiflow.live.snapshot import ScheduleSnapshot
from multiflow.validation.validator import Validator


class ScheduleFeatures(BaseModel):
    """Boring, stable feature vector for ranking and future learning."""

    schema_version: str = "multiflow.features.v1"
    task_count: int = 0
    resource_count: int = 0
    assignment_count: int = 0
    conflict_count: int = 0
    hard_constraint_count: int = 0
    soft_constraint_count: int = 0
    total_capacity: int = 0
    mean_utilization: float = 0.0
    max_utilization: float = 0.0
    unassigned_task_count: int = 0
    candidate_hard_violations: int = 0
    candidate_soft_penalty: float = 0.0
    candidate_objective_total: float = 0.0
    candidate_admissible: bool = False
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class FeatureExtractor:
    """Extract deterministic ScheduleFeatures from snapshot / problem / candidate."""

    def __init__(self, validator: Optional[Validator] = None) -> None:
        self.validator = validator or Validator()

    def extract(
        self,
        snapshot: Optional[ScheduleSnapshot] = None,
        problem: Optional[SchedulingProblem] = None,
        candidate: Optional[CandidateSolution] = None,
        conflict_count: int = 0,
    ) -> ScheduleFeatures:
        if snapshot is not None:
            problem = snapshot.problem
        if problem is None:
            raise ValueError("FeatureExtractor requires a snapshot or problem")

        task_count = len(problem.tasks)
        resource_count = len(problem.resources)
        assignment_count = 0
        if candidate is not None:
            assignment_count = len(candidate.assignments)
        else:
            assignment_count = len(problem.existing_assignments)

        hard_count = 0
        soft_count = 0
        for c in problem.constraints:
            sev = getattr(c, "severity", None)
            if sev is not None and str(getattr(sev, "value", sev)).lower() == "soft":
                soft_count += 1
            else:
                hard_count += 1

        total_capacity = sum(max(1, r.capacity) for r in problem.resources)
        utilization_by_res: dict[str, int] = {r.id: 0 for r in problem.resources}
        assignments = (
            candidate.assignments if candidate is not None else problem.existing_assignments
        )
        for a in assignments:
            for rid in a.resource_ids:
                if rid in utilization_by_res:
                    utilization_by_res[rid] += 1

        utils: list[float] = []
        for r in problem.resources:
            cap = max(1, r.capacity)
            utils.append(utilization_by_res.get(r.id, 0) / cap)
        mean_util = sum(utils) / len(utils) if utils else 0.0
        max_util = max(utils) if utils else 0.0

        assigned_tasks = {a.task_id for a in assignments}
        unassigned = sum(1 for t in problem.tasks if t.id not in assigned_tasks)

        cand_hard = 0
        cand_soft = 0.0
        cand_obj = 0.0
        cand_adm = False
        if candidate is not None:
            vr = self.validator.validate(problem, candidate)
            cand_hard = len(vr.hard_violations)
            cand_soft = vr.score.soft_penalty
            cand_obj = vr.score.total
            cand_adm = vr.admissible
            if candidate.score is not None:
                cand_obj = candidate.score.total

        return ScheduleFeatures(
            task_count=task_count,
            resource_count=resource_count,
            assignment_count=assignment_count,
            conflict_count=conflict_count,
            hard_constraint_count=hard_count,
            soft_constraint_count=soft_count,
            total_capacity=total_capacity,
            mean_utilization=round(mean_util, 6),
            max_utilization=round(max_util, 6),
            unassigned_task_count=unassigned,
            candidate_hard_violations=cand_hard,
            candidate_soft_penalty=cand_soft,
            candidate_objective_total=cand_obj,
            candidate_admissible=cand_adm,
        )
