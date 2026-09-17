"""CLI: multiflow solve <problem.json> [--solver classical|cp-sat|milp|quantum]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from multiflow.serialization.io import load_problem
from multiflow.solver.registry import available_solvers, get_solver
from multiflow.solver.result import SolverStatus
from multiflow.validation.validator import Validator


def cmd_solve(args: argparse.Namespace) -> int:
    path = Path(args.problem)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    problem = load_problem(path)

    solver_name = getattr(args, "solver", "classical")
    try:
        solver = get_solver(solver_name, max_candidates=getattr(args, "candidates", 5))
    except TypeError:
        try:
            solver = get_solver(solver_name)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = solver.solve_result(problem)
    validator = Validator()

    if result.status == SolverStatus.UNAVAILABLE:
        print(
            json.dumps(
                {
                    "status": "UNAVAILABLE",
                    "solver": result.solver_name,
                    "message": result.metadata.get("hint", "backend unavailable"),
                },
                indent=2,
            )
        )
        return 2

    task_ids = {t.id for t in problem.tasks}
    complete_admissible = []
    reports = []
    for c in result.candidates:
        vr = validator.validate(problem, c)
        c.score = vr.score
        placed = {a.task_id for a in c.assignments}
        complete = placed >= task_ids
        unplaced = sorted(task_ids - placed)
        entry = {
            "candidate_id": c.id,
            "admissible": vr.admissible,
            "complete": complete,
            "hard_violations": vr.score.hard_violations,
            "soft_penalty": vr.score.soft_penalty,
            "assignments": len(c.assignments),
            "tasks_total": len(problem.tasks),
            "unplaced_tasks": unplaced,
            "explanation_chain": vr.explanation_chain,
            "assignment_detail": [
                {
                    "task_id": a.task_id,
                    "resource_ids": a.resource_ids,
                    "start": a.window.start.isoformat(),
                    "end": a.window.end.isoformat(),
                    "schedule_id": a.schedule_id,
                }
                for a in c.assignments
            ],
        }
        reports.append(entry)
        if vr.admissible and complete:
            complete_admissible.append(entry)

    out = {
        "problem_id": problem.id,
        "solver": result.solver_name,
        "solver_version": result.solver_version,
        "solver_status": result.status.value,
        "runtime_seconds": result.runtime_seconds,
        "objective_value": result.objective_value,
        "candidates": reports,
    }

    if complete_admissible:
        out["outcome"] = "ADMISSIBLE"
        out["best"] = complete_admissible[0]
        code = 0
    elif any(r["admissible"] for r in reports):
        out["outcome"] = "PARTIAL_ADMISSIBLE"
        code = 1
    elif result.status == SolverStatus.INFEASIBLE:
        out["outcome"] = "NO_COMPLETE_SOLUTION"
        out["solver_reported"] = "INFEASIBLE"
        code = 1
    else:
        out["outcome"] = "NO_COMPLETE_SOLUTION"
        code = 1

    text = json.dumps(out, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(text)
        print(f"wrote {args.output}")
    else:
        print(text)
    return code


def cmd_list_solvers(_args: argparse.Namespace) -> int:
    for name in available_solvers():
        try:
            s = get_solver(name)
            print(f"{name:12} available  ({s.name} {s.version})")
        except (ValueError, ImportError, TypeError) as exc:
            print(f"{name:12} UNAVAILABLE  ({exc})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="multiflow", description="MultiFlow CLI")
    sub = parser.add_subparsers(dest="command")

    p_solve = sub.add_parser("solve", help="Solve a SchedulingProblem JSON file")
    p_solve.add_argument("problem", help="Path to problem JSON")
    p_solve.add_argument(
        "--solver",
        default="classical",
        help="Solver backend: classical | cp-sat | milp | quantum (default: classical)",
    )
    p_solve.add_argument(
        "--candidates", type=int, default=5, help="Max candidates (classical)"
    )
    p_solve.add_argument("-o", "--output", help="Write result JSON to path")
    p_solve.set_defaults(func=cmd_solve)

    p_list = sub.add_parser("solvers", help="List registered solvers")
    p_list.set_defaults(func=cmd_list_solvers)

    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
