import asyncio
from datetime import datetime, timezone

import pytest

from wyvern.contracts import WyvernEvent
from wyvern.services.event_emitter import EventEmitter


def _make_event(event_type: str = "mission.created") -> WyvernEvent:
    return WyvernEvent(
        event_type=event_type,
        mission_id="mis_test",
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_emit_and_subscribe():
    emitter = EventEmitter()
    q = emitter.subscribe()

    await emitter.emit(_make_event("mission.created"))
    event = q.get_nowait()
    assert event.event_type == "mission.created"
    assert event.seq == 1


@pytest.mark.asyncio
async def test_multiple_subscribers():
    emitter = EventEmitter()
    q1 = emitter.subscribe()
    q2 = emitter.subscribe()

    await emitter.emit(_make_event())
    assert q1.get_nowait().seq == 1
    assert q2.get_nowait().seq == 1


@pytest.mark.asyncio
async def test_ring_buffer_replay():
    emitter = EventEmitter(buffer_size=5)
    for i in range(10):
        await emitter.emit(_make_event(f"event_{i}"))

    recent = emitter.recent_events(since_seq=7)
    assert len(recent) == 3
    assert recent[0].event_type == "event_7"


@pytest.mark.asyncio
async def test_unsubscribe():
    emitter = EventEmitter()
    q = emitter.subscribe()
    emitter.unsubscribe(q)

    await emitter.emit(_make_event())
    assert q.empty()


@pytest.mark.asyncio
async def test_seq_monotonically_increases():
    emitter = EventEmitter()
    q = emitter.subscribe()

    await emitter.emit(_make_event())
    await emitter.emit(_make_event())
    await emitter.emit(_make_event())

    seqs = [q.get_nowait().seq for _ in range(3)]
    assert seqs == [1, 2, 3]
