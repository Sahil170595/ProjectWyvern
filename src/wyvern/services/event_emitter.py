from __future__ import annotations

import asyncio
from collections import deque

from wyvern.contracts import WyvernEvent


class EventEmitter:
    """In-memory pub/sub for control room event streaming."""

    def __init__(self, buffer_size: int = 100) -> None:
        self._subscribers: list[asyncio.Queue] = []
        self._seq = 0
        self._buffer: deque[WyvernEvent] = deque(maxlen=buffer_size)

    async def emit(self, event: WyvernEvent) -> None:
        self._seq += 1
        event.seq = self._seq
        self._buffer.append(event)
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue[WyvernEvent] = asyncio.Queue(maxsize=256)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def recent_events(self, since_seq: int = 0) -> list[WyvernEvent]:
        return [e for e in self._buffer if e.seq > since_seq]
