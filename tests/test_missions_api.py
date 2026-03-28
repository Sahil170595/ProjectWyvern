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
async def test_full_mission_lifecycle(client, mission_payload):
    # 1. Create mission
    resp = await client.post("/api/v1/missions", json=mission_payload)
    assert resp.status_code == 201
    data = resp.json()
    mission_id = data["mission_id"]

    # 2. Validate
    resp = await client.post(f"/api/v1/missions/{mission_id}/validate")
    assert resp.status_code == 200
    val = resp.json()
    assert val["passed"] is True

    # 3. Check state is awaiting_approval
    resp = await client.get(f"/api/v1/missions/{mission_id}/state")
    assert resp.json()["state"] == "awaiting_approval"

    # 4. Approve
    resp = await client.post(f"/api/v1/missions/{mission_id}/approve")
    assert resp.status_code == 200
    assert resp.json()["state"] == "approved"

    # 5. Execute
    resp = await client.post(f"/api/v1/missions/{mission_id}/execute")
    assert resp.status_code == 200
    assert resp.json()["state"] == "staging"

    # 6. Wait for completion (mock adapter completes quickly)
    for _ in range(50):
        await asyncio.sleep(0.1)
        resp = await client.get(f"/api/v1/missions/{mission_id}/state")
        if resp.json()["state"] == "completed":
            break
    assert resp.json()["state"] == "completed"

    # 7. Get timeline / replay artifact
    resp = await client.get(f"/api/v1/missions/{mission_id}/timeline")
    assert resp.status_code == 200
    replay = resp.json()
    assert replay["mission_hash"].startswith("sha256:")
    assert replay["summary"]["terminal_state"] == "completed"


@pytest.mark.asyncio
async def test_create_mission_returns_201(client, mission_payload):
    resp = await client.post("/api/v1/missions", json=mission_payload)
    assert resp.status_code == 201
    assert resp.json()["mission_id"] == "mis_test_001"


@pytest.mark.asyncio
async def test_get_nonexistent_mission_returns_404(client):
    resp = await client.get("/api/v1/missions/does_not_exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_approve_before_validate_returns_409(client, mission_payload):
    await client.post("/api/v1/missions", json=mission_payload)
    resp = await client.post("/api/v1/missions/mis_test_001/approve")
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_execute_before_approve_returns_409(client, mission_payload):
    await client.post("/api/v1/missions", json=mission_payload)
    await client.post("/api/v1/missions/mis_test_001/validate")
    resp = await client.post("/api/v1/missions/mis_test_001/execute")
    assert resp.status_code == 409
