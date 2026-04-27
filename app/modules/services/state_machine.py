"""Service state machine.

Allowed transitions::

    waiting       → in_progress, cancelled
    in_progress   → paused, completed, cancelled
    paused        → in_progress, completed, cancelled
    completed     → (terminal)
    cancelled     → (terminal)

Both ``completed`` and ``cancelled`` are terminal: any further transition is
rejected with code ``SERVICE_STATE_TERMINAL``. Invalid hops within the active
graph yield ``SERVICE_STATE_INVALID``. ``cancelled`` requires a non-empty
``reason`` (code ``SERVICE_CANCEL_REASON_REQUIRED``); ``paused`` accepts an
optional ``reason`` we surface to customers.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional

from app.core.errors import ConflictError, ValidationError

WAITING = "waiting"
IN_PROGRESS = "in_progress"
PAUSED = "paused"
COMPLETED = "completed"
CANCELLED = "cancelled"

TERMINAL: FrozenSet[str] = frozenset({COMPLETED, CANCELLED})

ALLOWED: Dict[str, FrozenSet[str]] = {
    WAITING: frozenset({IN_PROGRESS, CANCELLED}),
    IN_PROGRESS: frozenset({PAUSED, COMPLETED, CANCELLED}),
    PAUSED: frozenset({IN_PROGRESS, COMPLETED, CANCELLED}),
    COMPLETED: frozenset(),
    CANCELLED: frozenset(),
}


def validate(from_status: str, to_status: str, *, reason: Optional[str]) -> None:
    if from_status in TERMINAL:
        raise ConflictError(
            f"Service is {from_status}; no further transitions allowed",
            code="SERVICE_STATE_TERMINAL",
            details={"from": from_status, "to": to_status},
        )
    if to_status not in ALLOWED.get(from_status, frozenset()):
        raise ConflictError(
            f"Cannot transition {from_status} → {to_status}",
            code="SERVICE_STATE_INVALID",
            details={"from": from_status, "to": to_status},
        )
    if to_status == CANCELLED and not (reason and reason.strip()):
        raise ValidationError(
            "Cancellation requires a reason",
            code="SERVICE_CANCEL_REASON_REQUIRED",
        )
