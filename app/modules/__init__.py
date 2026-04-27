"""Domain modules.

Each sub-package is a bounded context that follows the strict four-layer split
documented in ``SYSTEM_ARCHITECTURE.md §3.4``:

    router  →  schemas  →  service  →  repository  →  models

Rules:
  * Routers never import ``models`` directly — only via ``service``.
  * Services never import another module's ``repository`` — only ``service``.
  * Cross-module writes go through events (Redis pub-sub or Arq jobs).
"""
