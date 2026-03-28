import asyncio
import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from wyvern.app import create_app
from wyvern.config import WyvernSettings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings():
    return WyvernSettings(use_mock_vehicle=True, telemetry_interval_ms=100)


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


@pytest.fixture
def mission_payload():
    return json.loads((FIXTURES / "sample_mission.json").read_text())


async def _advance_to_executing(client, mission_payload) -> str:
    """Helper: create -> validate -> approve -> execute, wait until executing."""
    resp = await client.post("/api/v1/missions", json=mission_payload)
    mission_id = resp.json()["mission_id"]
    await client.post(f"/api/v1/missions/{mission_id}/validate")
    await client.post(f"/api/v1/missions/{mission_id}/approve")
    await client.post(f"/api/v1/missions/{mission_id}/execute")

    # Wait for executing state
    for _ in range(30):
        await asyncio.sleep(0.05)
        resp = await client.get(f"/api/v1/missions/{mission_id}/state")
        if resp.json()["state"] == "executing":
            break
    return mission_id


@pytest.mark.asyncio
async def test_pause_and_resume(client, mission_payload):
    # Use a mission that won't auto-complete immediately
    mission_payload["route"]["waypoints"] = [
        {"seq": i, "lat": 42.3 + i * 0.0001, "lon": -71.1, "alt_m": 20, "hold_s": 0}
        for i in range(1, 21)  # 20 waypoints
    ]
    mission_id = await _advance_to_executing(client, mission_payload)

    # Pause
    resp = await client.post(f"/api/v1/missions/{mission_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["state"] == "paused"
    assert resp.json()["reason_code"] == "operator.pause"

    # Duplicate pause is idempotent
    resp = await client.post(f"/api/v1/missions/{mission_id}/pause")
    assert resp.status_code == 200
    assert resp.json()["reason_code"] == "idempotent.pause_duplicate"

    # Resume
    resp = await client.post(f"/api/v1/missions/{mission_id}/resume")
    assert resp.status_code == 200
    assert resp.json()["state"] == "executing"


@pytest.mark.asyncio
async def test_rtl_from_executing(client, mission_payload):
    mission_payload["route"]["waypoints"] = [
        {"seq": i, "lat": 42.3 + i * 0.0001, "lon": -71.1, "alt_m": 20, "hold_s": 0}
        for i in range(1, 21)
    ]
    mission_id = await _advance_to_executing(client, mission_payload)

    resp = await client.post(f"/api/v1/missions/{mission_id}/rtl")
    assert resp.status_code == 200
    assert resp.json()["state"] == "rtl"
    assert resp.json()["reason_code"] == "operator.rtl"


@pytest.mark.asyncio
async def test_abort_from_executing(client, mission_payload):
    mission_payload["route"]["waypoints"] = [
        {"seq": i, "lat": 42.3 + i * 0.0001, "lon": -71.1, "alt_m": 20, "hold_s": 0}
        for i in range(1, 21)
    ]
    mission_id = await _advance_to_executing(client, mission_payload)

    resp = await client.post(f"/api/v1/missions/{mission_id}/abort")
    assert resp.status_code == 200
    assert resp.json()["state"] == "aborted"
    assert resp.json()["reason_code"] == "operator.abort"

    # Check timeline shows operator intervention
    resp = await client.get(f"/api/v1/missions/{mission_id}/events")
    events = resp.json()["events"]
    abort_events = [e for e in events if e["reason_code"] == "operator.abort"]
    assert len(abort_events) == 1
