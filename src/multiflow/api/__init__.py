"""Versioned MultiFlow scheduling API (in-process).

Schema: multiflow.scheduling_api@1.0.0

Wraps LiveEngine + independent Validator. Solvers propose; validators admit.
NO_COMPLETE_SOLUTION remains first-class. No HTTP server required for
in-process consumers (Aurora adapter, demos).
"""

from .scheduling import (
    API_SCHEMA_ID,
    API_SCHEMA_VERSION,
    HealthStatus,
    SchedulingApi,
    SchedulingRequest,
    SchedulingResponse,
    SchedulingStatus,
)

__all__ = [
    "API_SCHEMA_ID",
    "API_SCHEMA_VERSION",
    "HealthStatus",
    "SchedulingApi",
    "SchedulingRequest",
    "SchedulingResponse",
    "SchedulingStatus",
]
