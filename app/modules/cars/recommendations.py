"""Mileage-based maintenance recommendations.

Ports the logic from ``front-user/src/lib/mockData.ts::getRecommendations``
and the service intervals list. Pure function — no DB.

The interval list below is intentionally conservative; product can tune
later. Each rule says: *every N km, the car should see <service_type>*. A
"due" item is one whose next-due mark is at or before current mileage; an
"upcoming" item comes within the next ``UPCOMING_WINDOW_KM`` km; anything
further is "optional".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class Interval:
    service_type: str
    interval_km: int
    reason_due: str
    reason_upcoming: str


# Order matters only for display — we group by priority afterwards.
INTERVALS: List[Interval] = [
    Interval("oil_change", 10_000, "Oil change is overdue", "Oil change is approaching"),
    Interval("air_filter", 20_000, "Air filter replacement is due", "Air filter soon"),
    Interval("cabin_filter", 20_000, "Cabin filter is due", "Cabin filter soon"),
    Interval("fuel_filter", 30_000, "Fuel filter replacement is due", "Fuel filter soon"),
    Interval("brake_pads", 30_000, "Brake pads inspection is due", "Brake pad inspection soon"),
    Interval("spark_plugs", 40_000, "Spark plugs should be replaced", "Spark plugs approaching"),
    Interval("transmission", 60_000, "Transmission service is due", "Transmission service soon"),
    Interval("timing_belt", 90_000, "Timing belt replacement is due", "Timing belt approaching"),
    Interval("coolant", 60_000, "Coolant flush is due", "Coolant flush soon"),
    Interval("wheel_alignment", 15_000, "Wheel alignment is due", "Wheel alignment soon"),
]

UPCOMING_WINDOW_KM = 1_500


def compute(mileage: int) -> List[dict]:
    """Return a list of recommendation dicts (in the shape of ``RecommendationItem``).

    ``mileage`` is in km. Negative/absent values are clamped to 0.
    """
    m = max(0, int(mileage or 0))
    out: List[dict] = []
    for itv in INTERVALS:
        # How many intervals have elapsed since delivery.
        elapsed = m // itv.interval_km
        # The next milestone on/after current mileage.
        next_due = (elapsed + 1) * itv.interval_km
        delta = next_due - m
        if m >= itv.interval_km and (m - elapsed * itv.interval_km) == 0:
            # Exactly at a milestone — treat as due.
            priority = "due"
            reason = itv.reason_due
        elif delta <= 0:
            priority = "due"
            reason = itv.reason_due
        elif delta <= UPCOMING_WINDOW_KM:
            priority = "upcoming"
            reason = itv.reason_upcoming
        else:
            priority = "optional"
            reason = f"Next {itv.service_type} at {next_due:,} km"
        out.append(
            {
                "service_type": itv.service_type,
                "reason": reason,
                "priority": priority,
                "interval_km": itv.interval_km,
                "next_due_km": next_due,
            }
        )
    # Sort: due first, then upcoming, then optional; preserve interval order inside a bucket.
    order = {"due": 0, "upcoming": 1, "optional": 2}
    out.sort(key=lambda r: (order[r["priority"]],))
    return out
