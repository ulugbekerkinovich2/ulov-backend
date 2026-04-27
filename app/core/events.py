"""Lightweight pub-sub wrapper over Redis.

Modules emit domain events (e.g. ``service.transitioned``) to channels; the
WebSocket layer and the notification dispatcher subscribe and fan them out.
Keeping this a tiny pair of helpers avoids coupling module code to Redis.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Iterable, Optional

from app.core.logging import get_logger

log = get_logger(__name__)

# Channel name conventions:
CH_SERVICES = "events:services:{center_id}"         # fan out to owners/mechanics dashboards
CH_SERVICE_ONE = "events:service:{service_id}"      # fan out to the one customer watching
CH_USER = "events:user:{user_id}"                  # fan out to a specific customer
CH_NOTIFICATIONS = "events:notifications"            # notification dispatcher
CH_CONTENT = "events:content"                        # cache invalidation for content module


def build_channel(template: str, **kwargs: Any) -> str:
    return template.format(**kwargs)


async def publish(redis: Any, channel: str, event: Dict[str, Any]) -> None:
    """Publish a JSON-serialised event to ``channel``."""
    payload = json.dumps(event, separators=(",", ":"), default=str)
    await redis.publish(channel, payload)
    log.debug("event_published", channel=channel, type=event.get("type"))


async def subscribe(
    redis: Any, channels: Iterable[str]
) -> AsyncIterator[Dict[str, Any]]:
    """Subscribe and yield decoded events until the caller stops iterating.

    Uses ``redis.pubsub()`` with decode_responses turned on at the client. The
    caller is responsible for cancelling the async generator (e.g. when a WS
    client disconnects).
    """
    pubsub = redis.pubsub()
    try:
        await pubsub.subscribe(*channels)
        async for raw in pubsub.listen():
            if raw is None:
                continue
            if raw.get("type") != "message":
                continue
            data = raw.get("data")
            if isinstance(data, bytes):
                data = data.decode("utf-8")
            try:
                yield json.loads(data) if isinstance(data, str) else data
            except json.JSONDecodeError:
                log.warning("event_decode_error", channel=raw.get("channel"))
    finally:
        try:
            await pubsub.unsubscribe()
            await pubsub.close()
        except Exception:  # noqa: BLE001
            pass


def make_event(
    type_: str,
    payload: Optional[Dict[str, Any]] = None,
    **meta: Any,
) -> Dict[str, Any]:
    """Uniform event envelope.

    ``type_`` is a dotted string (``service.transitioned``). ``payload``
    carries domain data; ``meta`` is merged at top level (e.g. ``event_id``,
    ``at``, ``actor_id``).
    """
    return {"type": type_, "payload": payload or {}, **meta}
