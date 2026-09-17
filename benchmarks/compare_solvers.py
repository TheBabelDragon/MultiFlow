"""Cross-backend comparison harness. Reports measurements only."""

from __future__ import annotations

import argparse

from multiflow import SchedulingProblem, Validator, available_solvers, get_solver
from multiflow.solver.result import SolverStatus


def compare(problem_path: str, solvers: list[str] | None = None) -> list[dict]:
    problem = SchedulingProblem.from_json(problem_path)
    names = solvers or available_solvers()
    validator = Validator()
    rows = []
    for name in names:
        row = {
            "solver": name,
            "status": "—",
            "objective": "—",
            "runtime": "—",
            "candidates": 0,
            "validation": "—",
        }
        try:
            solver = get_solver(name)
        except ValueError as exc:
            row["status"] = "UNAVAILABLE"
            row["validation"] = str(exc).split("\n")[0][:40]
            rows.append(row)
            continue
        result = solver.solve_result(problem)
        row["status"] = result.status.value
        row["runtime"] = (
            f"{result.runtime_seconds:.4f}s" if result.runtime_seconds is not None else "—"
        )
        row["objective"] = result.objective_value if result.objective_value is not None else "—"
        row["candidates"] = len(result.candidates)
        if result.status == SolverStatus.UNAVAILABLE:
            row["validation"] = "—"
        elif not result.candidates:
            row["validation"] = "NO_CANDIDATE"
        else:
            vr = validator.validate(problem, result.candidates[0])
            row["validation"] = "ADMISSIBLE" if vr.admissible else "REJECTED"
        rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare MultiFlow solver backends")
    parser.add_argument(
        "problem",
        nargs="?",
        default="examples/solver-benchmark.json",
        help="Path to SchedulingProblem JSON",
    )
    parser.add_argument("--solvers", nargs="*", help="Subset of solvers to run")
    args = parser.parse_args()
    rows = compare(args.problem, args.solvers)
    print(f"{'Solver':12} {'Status':12} {'Objective':12} {'Runtime':12} {'Cands':6} {'Validation'}")
    print("-" * 70)
    for r in rows:
        print(
            f"{r['solver']:12} {r['status']:12} {str(r['objective']):12} "
            f"{r['runtime']:12} {r['candidates']:6} {r['validation']}"
        )


if __name__ == "__main__":
    main()
