"""Explicit solver registry — no dynamic plugin discovery."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from multiflow.solver.interface import Solver

_REGISTRY: dict[str, type] = {}


def register(name: str, cls: type) -> None:
    _REGISTRY[name] = cls


def available_solvers() -> list[str]:
    return sorted(set(_REGISTRY.keys()))


def get_solver(name: str = "classical", **kwargs) -> "Solver":
    """Return a solver instance by name.

    Raises ValueError with install hints for optional backends whose
    dependencies are missing.
    """
    key = name.lower().replace("_", "-")
    aliases = {"cpsat": "cp-sat"}
    key = aliases.get(key, key)

    if key not in _REGISTRY:
        known = ", ".join(sorted(set(_REGISTRY.keys()))) or "(none)"
        raise ValueError(
            f"Unknown solver '{name}'. Known: {known}."
        )
    cls = _REGISTRY[key]
    try:
        return cls(**kwargs)
    except TypeError:
        return cls()
    except ImportError as exc:
        hint = {
            "cp-sat": 'Install the optional CP-SAT dependency:\n    pip install "multiflow[cp-sat]"',
            "milp": 'Install the optional MILP dependency:\n    pip install "multiflow[milp]"',
            "quantum": "Quantum companion not configured.",
        }.get(key, "")
        raise ValueError(
            f"Solver '{name}' is unavailable.\n{exc}\n{hint}"
        ) from exc


def _bootstrap() -> None:
    from multiflow.solver.classical import ClassicalSolver
    from multiflow.solver.quantum import QuantumSolver

    register("classical", ClassicalSolver)
    register("quantum", QuantumSolver)

    try:
        import ortools  # noqa: F401
        from multiflow.solver.cpsat import CPSATSolver
        register("cp-sat", CPSATSolver)
    except ImportError:
        from multiflow.solver.stubs import UnavailableSolver

        class _CPSATMissing(UnavailableSolver):
            name = "cp-sat"
            install_hint = 'pip install "multiflow[cp-sat]"'

        register("cp-sat", _CPSATMissing)

    try:
        import pulp  # noqa: F401
        from multiflow.solver.milp import MILPSolver
        register("milp", MILPSolver)
    except ImportError:
        from multiflow.solver.stubs import UnavailableSolver

        class _MILPMissing(UnavailableSolver):
            name = "milp"
            install_hint = 'pip install "multiflow[milp]"'

        register("milp", _MILPMissing)


_bootstrap()
