"""Dump the FastAPI OpenAPI schema to ``openapi.json`` at repo root.

Frontends consume this file to generate typed clients.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False))
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
