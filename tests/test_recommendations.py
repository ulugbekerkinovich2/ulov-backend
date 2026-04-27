"""Cars recommendations — pure function, no DB."""

from __future__ import annotations

from app.modules.cars.recommendations import INTERVALS, UPCOMING_WINDOW_KM, compute


def test_zero_mileage_is_all_optional() -> None:
    items = compute(0)
    assert len(items) == len(INTERVALS)
    # No "due" items at km 0 — first milestone is at interval_km.
    assert all(i["priority"] != "due" for i in items)


def test_oil_change_due_at_10k() -> None:
    items = compute(10_000)
    oil = next(i for i in items if i["service_type"] == "oil_change")
    assert oil["priority"] == "due"


def test_upcoming_window_detected() -> None:
    mileage = 10_000 - UPCOMING_WINDOW_KM  # within window
    items = compute(mileage)
    oil = next(i for i in items if i["service_type"] == "oil_change")
    assert oil["priority"] == "upcoming"


def test_items_ordered_due_before_upcoming_before_optional() -> None:
    items = compute(15_000)  # 15k: oil overdue, air filter due soon, others far
    priorities = [i["priority"] for i in items]
    # Once the priority transitions, it must not revert.
    transitions = [
        (priorities[i], priorities[i + 1]) for i in range(len(priorities) - 1)
    ]
    order = {"due": 0, "upcoming": 1, "optional": 2}
    for a, b in transitions:
        assert order[a] <= order[b]


def test_every_item_has_next_due_km() -> None:
    for itv in compute(42_000):
        assert itv["next_due_km"] is not None
        assert itv["interval_km"] is not None
        assert itv["next_due_km"] > 0
