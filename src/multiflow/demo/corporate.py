"""Corporate multi-schedule demo for MultiFlow."""

from __future__ import annotations

import sys
from pathlib import Path

from multiflow.domain.models import SchedulingProblem
from multiflow.solver.registry import get_solver
from multiflow.validation.validator import Validator


def _find_example(name: str) -> Path:
    candidates = [
        Path("examples") / name,
        Path(__file__).resolve().parents[3] / "examples" / name,
        Path.cwd() / "examples" / name,
    ]
    for p in candidates:
        if p.is_file():
            return p
    raise FileNotFoundError(f"Could not locate examples/{name}")


def main() -> int:
    path = _find_example("corporate.json")
    problem = SchedulingProblem.from_json(str(path))
    solver = get_solver("classical")
    result = solver.solve_result(problem)
    validator = Validator()

    print(f"Problem: {problem.id}")
    print(f"Resources: {len(problem.resources)}  Tasks: {len(problem.tasks)}  Schedules: {len(problem.schedules)}")
    print(f"Solver status: {result.status.value}")
    print(f"Candidates: {len(result.candidates)}")

    admissible = 0
    for cand in result.candidates:
        vr = validator.validate(problem, cand)
        status = "ADMISSIBLE" if vr.admissible else "REJECTED"
        if vr.admissible:
            admissible += 1
        print(f"  {cand.id}: {status}  assignments={len(cand.assignments)}")
        if not vr.admissible and vr.explanation_chain:
            print(f"    reason: {vr.explanation_chain[0]}")

    print(f"Admissible candidates: {admissible}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
