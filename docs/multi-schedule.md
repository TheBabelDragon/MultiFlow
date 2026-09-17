# Multi-schedule arbitration

Independent schedules may share resources.

A `ScheduleConflict` records schedule_a/b, resource, time range, conflicting assignments, constraint, severity, explanation, possible_resolutions.

The `Arbitrator` detects, explains, asks the classical solver for alternatives, and re-validates every candidate.
