from __future__ import annotations

import json
from pathlib import Path

import pytest

from wyvern.contracts import Mission
from wyvern.store import MissionStore, VehicleTelemetryCache
from wyvern.vehicle.mock_adapter import MockVehicleAdapter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_adapter():
    adapter = MockVehicleAdapter(vehicle_id="veh_test_001")
    return adapter


@pytest.fixture
def mission_store():
    return MissionStore()


@pytest.fixture
def telemetry_cache():
    return VehicleTelemetryCache()


@pytest.fixture
def sample_mission_data():
    return json.loads((FIXTURES / "sample_mission.json").read_text())


@pytest.fixture
def sample_mission(sample_mission_data):
    return Mission(**sample_mission_data)
