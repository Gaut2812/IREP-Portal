"""Realtime hub: WebSocket fan-out by channel.

The in-process hub is enough for a single API worker (development and the
pilot). REALTIME_ADAPTER=valkey switches to Valkey pub/sub once more than one
worker runs; the public API (`publish`, `subscribe`) does not change.
"""
import asyncio
import json
from collections import defaultdict
from typing import Any, Dict, Set

from fastapi import WebSocket


class InProcessHub:
    def __init__(self) -> None:
        self._channels: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def subscribe(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        self._channels[channel].add(ws)

    async def unsubscribe(self, channel: str, ws: WebSocket) -> None:
        self._channels[channel].discard(ws)
        if not self._channels[channel]:
            self._channels.pop(channel, None)

    async def publish(self, channel: str, payload: Dict[str, Any]) -> int:
        """Send a JSON payload to every subscriber. Returns the receiver count."""
        message = json.dumps(payload, default=str)
        dead = []
        subscribers = list(self._channels.get(channel, ()))
        for ws in subscribers:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.unsubscribe(channel, ws)
        return len(subscribers) - len(dead)

    def subscriber_count(self, channel: str) -> int:
        return len(self._channels.get(channel, ()))


hub = InProcessHub()


def publish_sync(channel: str, payload: Dict[str, Any]) -> None:
    """Fire-and-forget publish from synchronous route handlers.

    Sync routes run in a worker thread, so we hand the coroutine to the main
    event loop when one is running; otherwise the publish is a no-op.
    """
    loop = _MAIN_LOOP.get("loop")
    if loop is None or loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(hub.publish(channel, payload), loop)
    except RuntimeError:
        pass


_MAIN_LOOP: Dict[str, Any] = {"loop": None}


def register_event_loop() -> None:
    """Call once from the FastAPI lifespan so sync handlers can publish."""
    try:
        _MAIN_LOOP["loop"] = asyncio.get_running_loop()
    except RuntimeError:
        _MAIN_LOOP["loop"] = None
