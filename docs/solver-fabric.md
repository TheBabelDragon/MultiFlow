# Solver fabric

```python
class Solver(ABC):
    def solve(self, problem: SchedulingProblem) -> list[CandidateSolution]: ...
    def metadata(self) -> dict: ...
```

MVP implements `ClassicalSolver` (deterministic greedy + variants).

Quantum companion boundary: consumes the same `SchedulingProblem`; never owns scheduling semantics.
