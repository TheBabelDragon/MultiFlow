"""CLI: multiflow solve <problem.json>"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from multiflow.serialization.io import load_problem
from multiflow.solver.classical import ClassicalSolver
from multiflow.validation.validator import Validator


def cmd_solve(args: argparse.Namespace) -> int:
    path = Path(args.problem)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2

    problem = load_problem(path)
    solver = ClassicalSolver(max_candidates=args.candidates)
    candidates = solver.solve(problem)
    validator = Validator()

    task_ids = {t.id for t in problem.tasks}
    complete_admissible = []
    reports = []
    for c in candidates:
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

    if complete_admissible:
        status = "ADMISSIBLE"
    elif any(r["admissible"] for r in reports):
        status = "NO_COMPLETE_SOLUTION"
    else:
        status = "NO_ADMISSIBLE_SOLUTION"

    result = {
        "schema_version": "multiflow.solve_result.v1",
        "problem_id": problem.id,
        "solver": solver.metadata(),
        "candidate_count": len(reports),
        "admissible_count": sum(1 for r in reports if r["admissible"]),
        "complete_admissible_count": len(complete_admissible),
        "status": status,
        "candidates": reports,
    }

    if args.output:
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
        print(f"wrote {args.output}")
    else:
        print(json.dumps(result, indent=2))

    if status != "ADMISSIBLE":
        print(f"\n{status}", file=sys.stderr)
        if reports:
            best = reports[0]
            if best.get("unplaced_tasks"):
                print(f"Unplaced tasks: {best['unplaced_tasks']}", file=sys.stderr)
            if best.get("explanation_chain"):
                print("Blocking constraints (best candidate):", file=sys.stderr)
                for line in best["explanation_chain"][:8]:
                    print(f"  – {line}", file=sys.stderr)
            else:
                print(
                    "Capacity/availability exhausted before all tasks could be placed.",
                    file=sys.stderr,
                )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="multiflow",
        description="MultiFlow – general-purpose scheduling and constraint arbitration",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    solve_p = sub.add_parser("solve", help="Solve a JSON SchedulingProblem")
    solve_p.add_argument("problem", help="Path to problem JSON")
    solve_p.add_argument("-o", "--output", help="Write result JSON to path")
    solve_p.add_argument(
        "-n", "--candidates", type=int, default=5, help="Max candidates to generate"
    )
    solve_p.set_defaults(func=cmd_solve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
