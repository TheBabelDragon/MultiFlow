# Domain model

All entities carry an explicit `schema_version` (e.g. `multiflow.task.v1`).

## Resource

May represent a worker, team, room, vehicle, machine, GPU, facility, slot, external service, etc.

Fields: id, type, name, availability, capabilities, capacity, location, attributes.

## Task

Work that needs resources inside allowed windows.

## Assignment

task_id + resource_ids + concrete TimeWindow (+ optional schedule_id).

## SchedulingProblem

Normalized input to every solver.

## CandidateSolution / ValidationResult

Solver output is never trusted until the Validator has produced a `ValidationResult`.
