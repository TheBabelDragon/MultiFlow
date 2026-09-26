"""Live recalculation demonstration for MultiFlow.

1. Load examples/corporate.json
2. Construct LiveEngine
3. Print initial admissible result
4. Apply RESOURCE_UNAVAILABLE to shared resource forklift-17
5. Recalculate and print results
6. Demonstrate deterministic replay
"""

from __future__ import annotations

import sys
from pathlib import Path

from multiflow.domain.models import SchedulingProblem
from multiflow.live.decision import DecisionSource
from multiflow.live.engine import LiveEngine
from multiflow.live.events import EventType, SchedulingEvent


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
    engine = LiveEngine(initial_problem=problem)

    print("=== Initial recalculation ===")
    initial = engine.recalculate()
    print(f"Candidates: {len(initial['candidates'])}")
    print(f"Admissible: {len(initial['admissible'])}")
    print(f"Has admissible plan: {initial['has_admissible_plan']}")
    if initial["ranked"]:
        best, score = initial["ranked"][0]
        print(f"Selected deterministic candidate: {best.id} (score={score:.2f})")
        engine.record_decision(
            selected_candidate_id=best.id,
            source=DecisionSource.DETERMINISTIC_SCORER,
            scores={c.id: s for c, s in initial["ranked"]},
        )
    else:
        print("No admissible candidate")

    # Live disruption: forklift goes offline
    event = SchedulingEvent(
        event_type=EventType.RESOURCE_UNAVAILABLE,
        entity_ids=["forklift-17"],
        attributes={"resource_id": "forklift-17"},
        source="ops",
        reason="maintenance",
    )
    print("\n=== Apply RESOURCE_UNAVAILABLE ===")
    engine.apply_event(event)
    print(f"Event: {event.event_type.value}")
    print(f"Affected resource: forklift-17")
    print(f"Reason: {event.reason}")

    result = engine.recalculate()
    print(f"\nCandidate count: {len(result['candidates'])}")
    print(f"Admissible candidate count: {len(result['admissible'])}")
    print(f"Rejected candidates: {len(result['rejected'])}")
    for cid, reason in result["rejected"].items():
        print(f"  REJECTED {cid}: {reason}")
    if result["ranked"]:
        best, score = result["ranked"][0]
        print(f"Selected deterministic candidate: {best.id} (score={score:.2f})")
        for a in best.assignments:
            print(f"  assignment task={a.task_id} resources={a.resource_ids}")
        engine.record_decision(
            selected_candidate_id=best.id,
            source=DecisionSource.DETERMINISTIC_SCORER,
            scores={c.id: s for c, s in result["ranked"]},
        )
    else:
        print("No admissible plan after disruption (infeasible recalculation)")
        print(f"Has admissible plan: {result['has_admissible_plan']}")

    print("\n=== Deterministic replay ===")
    events = engine.event_store.events
    op_events = [e for e in events if e.event_type != EventType.HUMAN_OVERRIDE]
    replayed = LiveEngine.replay(problem, op_events)
    original_state = engine.semantic_state()
    replay_state = replayed.semantic_state()
    match = (
        original_state["resource_availability"] == replay_state["resource_availability"]
        and original_state["resource_capacity"] == replay_state["resource_capacity"]
        and original_state["task_ids"] == replay_state["task_ids"]
    )
    print(f"Replay semantic state matches: {match}")
    if not match:
        print("  original resource avail:", original_state["resource_availability"])
        print("  replayed resource avail:", replay_state["resource_availability"])
        return 1

    print("\nMetrics:", engine.metrics.snapshot())
    print("Live recalculation demo completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
