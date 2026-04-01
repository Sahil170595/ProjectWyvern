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


@pytest.mark.asyncio
async def test_vehicle_panel_no_telemetry(client):
    resp = await client.get("/api/v1/control-room/vehicles/veh_unknown/panel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["vehicle_id"] == "veh_unknown"
    assert data["vehicle_state"] is None
    assert data["active_mission_id"] is None


@pytest.mark.asyncio
async def test_fleet_status_empty(client):
    resp = await client.get("/api/v1/control-room/fleet")
    assert resp.status_code == 200
    assert resp.json()["vehicles"] == []


@pytest.mark.asyncio
async def test_fleet_status_with_mission(client, mission_payload):
    await client.post("/api/v1/missions", json=mission_payload)
    resp = await client.get("/api/v1/control-room/fleet")
    assert resp.status_code == 200
    vehicles = resp.json()["vehicles"]
    assert len(vehicles) == 1
    assert vehicles[0]["vehicle_id"] == "veh_px4_sitl_001"


@pytest.mark.asyncio
async def test_mission_incidents_empty(client, mission_payload):
    await client.post("/api/v1/missions", json=mission_payload)
    resp = await client.get("/api/v1/control-room/missions/mis_test_001/incidents")
    assert resp.status_code == 200
    assert resp.json()["incidents"] == []


@pytest.mark.asyncio
async def test_mission_full_state(client, mission_payload):
    await client.post("/api/v1/missions", json=mission_payload)
    resp = await client.get("/api/v1/control-room/missions/mis_test_001/state")
    assert resp.status_code == 200
    data = resp.json()
    assert data["state"] == "draft"
    assert data["incident_count"] == 0
    assert data["timeline_entries"] >= 1
