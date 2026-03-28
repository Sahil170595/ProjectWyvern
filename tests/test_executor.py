import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from wyvern.contracts import (
    Health,
    Mission,
    MissionProgress,
    Position,
    TelemetryEvent,
    Velocity,
    VehicleState,
)
from wyvern.services.executor import MissionExecutor
from wyvern.services.safety_guard import SafetyGuard
from wyvern.state_machine import MissionState
from wyvern.store import MissionStore, VehicleTelemetryCache
from wyvern.vehicle.mock_adapter import MockVehicleAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def _load_mission() -> Mission:
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    return Mission(**data)


def _seed_telemetry(cache: VehicleTelemetryCache, vehicle_id: str = "veh_px4_sitl_001"):
    cache.update(vehicle_id, TelemetryEvent(
        event_id="evt_seed",
        trace_id="trc_test",
        mission_id="mis_test_001",
        vehicle_id=vehicle_id,
        timestamp=datetime.now(timezone.utc),
        vehicle_state=VehicleState(mode="idle", armed=False, in_air=False),
        position=Position(lat=42.3, lon=-71.1, alt_m=0),
        velocity=Velocity(ground_speed_mps=0, vertical_speed_mps=0),
        health=Health(
            battery_percent=90,
            gps_fix="3d",
            telemetry_age_ms=50,
            link_quality=0.95,
            estimator_status="nominal",
        ),
        mission_progress=MissionProgress(state="idle", current_waypoint=0, waypoints_total=0),
    ))


@pytest.mark.asyncio
async def test_executor_happy_path():
    adapter = MockVehicleAdapter(vehicle_id="veh_px4_sitl_001")
    await adapter.connect()
    store = MissionStore()
    cache = VehicleTelemetryCache()
    _seed_telemetry(cache)
    guard = SafetyGuard(cache)
    executor = MissionExecutor(adapter, store, guard)

    mission = _load_mission()
    store.create(mission)
    # Advance through states to STAGING
    store.transition("mis_test_001", MissionState.VALIDATED, "test", "test")
    store.transition("mis_test_001", MissionState.AWAITING_APPROVAL, "test", "test")
    store.transition("mis_test_001", MissionState.APPROVED, "test", "test")
    store.transition("mis_test_001", MissionState.STAGING, "wyvern_executor", "test")

    await executor.execute("mis_test_001")

    record = store.get("mis_test_001")
    assert record is not None
    assert record.state == MissionState.COMPLETED


@pytest.mark.asyncio
async def test_executor_respects_pause():
    adapter = MockVehicleAdapter(vehicle_id="veh_px4_sitl_001")
    adapter._advance_on_poll = False  # Don't auto-complete
    await adapter.connect()
    store = MissionStore()
    cache = VehicleTelemetryCache()
    _seed_telemetry(cache)
    guard = SafetyGuard(cache)
    executor = MissionExecutor(adapter, store, guard)

    mission = _load_mission()
    store.create(mission)
    store.transition("mis_test_001", MissionState.VALIDATED, "test", "test")
    store.transition("mis_test_001", MissionState.AWAITING_APPROVAL, "test", "test")
    store.transition("mis_test_001", MissionState.APPROVED, "test", "test")
    store.transition("mis_test_001", MissionState.STAGING, "wyvern_executor", "test")

    # Run executor in background, then pause after a short delay
    async def pause_after_delay():
        await asyncio.sleep(0.3)
        store.transition("mis_test_001", MissionState.PAUSED, "operator", "operator.pause")

    task = asyncio.create_task(executor.execute("mis_test_001"))
    pause_task = asyncio.create_task(pause_after_delay())

    await asyncio.gather(task, pause_task)

    record = store.get("mis_test_001")
    assert record is not None
    assert record.state == MissionState.PAUSED


@pytest.mark.asyncio
async def test_executor_low_battery_triggers_rtl():
    adapter = MockVehicleAdapter(vehicle_id="veh_px4_sitl_001")
    adapter._advance_on_poll = False
    adapter.set_battery(90.0)
    adapter.set_drain_rate(30.0)  # Aggressive drain
    await adapter.connect()
    store = MissionStore()
    cache = VehicleTelemetryCache()
    _seed_telemetry(cache)
    guard = SafetyGuard(cache)
    executor = MissionExecutor(adapter, store, guard)

    mission = _load_mission()
    store.create(mission)
    store.transition("mis_test_001", MissionState.VALIDATED, "test", "test")
    store.transition("mis_test_001", MissionState.AWAITING_APPROVAL, "test", "test")
    store.transition("mis_test_001", MissionState.APPROVED, "test", "test")
    store.transition("mis_test_001", MissionState.STAGING, "wyvern_executor", "test")

    # Update telemetry cache with low battery during execution
    async def drain_battery():
        await asyncio.sleep(0.2)
        cache.update("veh_px4_sitl_001", TelemetryEvent(
            event_id="evt_low",
            trace_id="trc_test",
            mission_id="mis_test_001",
            vehicle_id="veh_px4_sitl_001",
            timestamp=datetime.now(timezone.utc),
            vehicle_state=VehicleState(mode="mission", armed=True, in_air=True),
            position=Position(lat=42.3, lon=-71.1, alt_m=22),
            velocity=Velocity(ground_speed_mps=5, vertical_speed_mps=0),
            health=Health(
                battery_percent=10.0,
                gps_fix="3d",
                telemetry_age_ms=50,
                link_quality=0.95,
                estimator_status="nominal",
            ),
            mission_progress=MissionProgress(state="executing", current_waypoint=1, waypoints_total=3),
        ))

    task = asyncio.create_task(executor.execute("mis_test_001"))
    drain_task = asyncio.create_task(drain_battery())

    await asyncio.gather(task, drain_task)

    record = store.get("mis_test_001")
    assert record is not None
    assert record.state == MissionState.RTL
    # Check timeline has safety_guard entry
    rtl_entries = [e for e in record.timeline if e.reason_code.startswith("degraded.")]
    assert len(rtl_entries) >= 1
