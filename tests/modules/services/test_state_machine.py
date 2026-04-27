"""Pure-function tests for the service state-machine validator."""

from __future__ import annotations

import pytest

from app.core.errors import ConflictError, ValidationError
from app.modules.services import state_machine as sm


@pytest.mark.parametrize(
    "from_, to_",
    [
        ("waiting", "in_progress"),
        ("waiting", "cancelled"),
        ("in_progress", "paused"),
        ("in_progress", "completed"),
        ("in_progress", "cancelled"),
        ("paused", "in_progress"),
        ("paused", "completed"),
        ("paused", "cancelled"),
    ],
)
def test_valid_transitions(from_: str, to_: str) -> None:
    sm.validate(from_, to_, reason="x" if to_ == "cancelled" else None)


@pytest.mark.parametrize(
    "from_, to_",
    [
        ("waiting", "paused"),
        ("waiting", "completed"),
        ("paused", "waiting"),
        ("in_progress", "waiting"),
    ],
)
def test_invalid_hops(from_: str, to_: str) -> None:
    with pytest.raises(ConflictError) as ex:
        sm.validate(from_, to_, reason=None)
    assert ex.value.code == "SERVICE_STATE_INVALID"


@pytest.mark.parametrize("terminal", ["completed", "cancelled"])
def test_terminal_blocks_further(terminal: str) -> None:
    with pytest.raises(ConflictError) as ex:
        sm.validate(terminal, "in_progress", reason=None)
    assert ex.value.code == "SERVICE_STATE_TERMINAL"


def test_cancel_requires_reason() -> None:
    with pytest.raises(ValidationError) as ex:
        sm.validate("in_progress", "cancelled", reason="")
    assert ex.value.code == "SERVICE_CANCEL_REASON_REQUIRED"


def test_cancel_with_reason_ok() -> None:
    sm.validate("in_progress", "cancelled", reason="customer requested")
