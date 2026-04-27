"""Static reference data.

Three datasets the frontend pickers need but that don't change often enough
to deserve their own table:

  * ``GET /reference/vehicle-brands`` — top + other + flat list.
  * ``GET /reference/vehicle-colors`` — common car colours.
  * ``GET /reference/service-intervals`` — recommended km between
    services (motor oil, air filter, etc).

The data is loaded **once at module import** from ``data.json`` at the
project root, so the file lives outside the container's ``/app`` source.
We fall back to an embedded minimal default if the file is missing — keeps
tests + dev green even without seed data mounted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter()


# ---------------------------------------------------------------------------
# Data loading — best-effort, with sane defaults
# ---------------------------------------------------------------------------
_DEFAULT_BRANDS: Dict[str, Any] = {"top": [], "other": [], "all": []}
_DEFAULT_COLORS: List[str] = [
    "Oq",
    "Qora",
    "Kulrang",
    "Kumush",
    "Qizil",
    "Ko'k",
]
_DEFAULT_INTERVALS: Dict[str, int] = {
    "Motor moyi almashtirish": 10000,
    "Havo filtri": 15000,
    "Tormoz kolodkalari": 30000,
    "Tasma": 60000,
    "Tormoz suyuqligi": 40000,
}


def _candidate_data_paths() -> List[Path]:
    """Search a couple of plausible locations for ``data.json``.

    The Docker image doesn't ship with seed data; we accept either a mount at
    the repo root or a custom path via ``ULOV_SEED_PATH`` env var.
    """
    import os

    paths: List[Path] = []
    env_path = os.environ.get("ULOV_SEED_PATH")
    if env_path:
        paths.append(Path(env_path))
    here = Path(__file__).resolve()
    # backend/app/modules/reference/router.py → repo root is 4 levels up.
    paths.append(here.parents[4] / "data.json")
    paths.append(here.parents[3] / "data.json")
    paths.append(Path("/data.json"))
    return paths


def _load() -> Dict[str, Any]:
    for path in _candidate_data_paths():
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return {}


_DATA = _load()
_BRANDS = _DATA.get("vehicleBrands") or _DEFAULT_BRANDS
_COLORS = _DATA.get("vehicleColors") or _DEFAULT_COLORS
_INTERVALS = _DATA.get("serviceIntervals") or _DEFAULT_INTERVALS


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/vehicle-brands",
    summary="Vehicle brand catalogue (top + other + flat)",
)
def vehicle_brands() -> Dict[str, Any]:
    return _BRANDS


@router.get(
    "/vehicle-colors",
    summary="Common vehicle colours (Uzbek labels)",
)
def vehicle_colors() -> List[str]:
    return list(_COLORS)


@router.get(
    "/service-intervals",
    summary="Recommended km between maintenance items",
)
def service_intervals() -> Dict[str, int]:
    return dict(_INTERVALS)
