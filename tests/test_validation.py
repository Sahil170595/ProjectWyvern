import json
from datetime import datetime, timezone
from pathlib import Path

from wyvern.contracts import (
    CheckStatus,
    Health,
    Mission,
    MissionProgress,
    Position,
    TelemetryEvent,
    Velocity,
    VehicleState,
)
from wyvern.services.validation import ValidationService, _point_in_polygon
from wyvern.store import VehicleTelemetryCache

FIXTURES = Path(__file__).parent / "fixtures"


def _make_telemetry(vehicle_id: str = "veh_px4_sitl_001", battery: float = 90.0) -> TelemetryEvent:
    return TelemetryEvent(
        event_id="evt_test",
        trace_id="trc_test",
        mission_id="mis_test",
        vehicle_id=vehicle_id,
        timestamp=datetime.now(timezone.utc),
        vehicle_state=VehicleState(mode="idle", armed=False, in_air=False),
        position=Position(lat=42.3, lon=-71.1, alt_m=0),
        velocity=Velocity(ground_speed_mps=0, vertical_speed_mps=0),
        health=Health(
            battery_percent=battery,
            gps_fix="3d",
            telemetry_age_ms=50,
            link_quality=0.95,
            estimator_status="nominal",
        ),
        mission_progress=MissionProgress(state="idle", current_waypoint=0, waypoints_total=0),
    )


def _load_mission() -> Mission:
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    return Mission(**data)


def test_validation_passes_with_good_telemetry():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache)
    mission = _load_mission()
    result = svc.validate(mission)
    assert result.passed
    assert all(c.status != CheckStatus.FAILED for c in result.checks)


def test_validation_warns_without_telemetry():
    cache = VehicleTelemetryCache()
    svc = ValidationService(cache)
    mission = _load_mission()
    result = svc.validate(mission)
    # Should pass with warnings (no telemetry = warning, not failure)
    assert result.passed
    warnings = [c for c in result.checks if c.status == CheckStatus.WARNING]
    assert len(warnings) >= 1


def test_validation_fails_low_battery():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry(battery=10.0))
    svc = ValidationService(cache)
    mission = _load_mission()
    result = svc.validate(mission)
    assert not result.passed
    failed = [c for c in result.checks if c.status == CheckStatus.FAILED]
    assert any("battery" in c.name for c in failed)


def test_validation_fails_waypoint_outside_geofence():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache)
    mission = _load_mission()
    # Move a waypoint way outside the geofence
    mission.route.waypoints[0].lat = 50.0
    mission.route.waypoints[0].lon = 10.0
    result = svc.validate(mission)
    assert not result.passed
    failed = [c for c in result.checks if c.status == CheckStatus.FAILED]
    assert any("geofence" in c.name for c in failed)


def test_validation_fails_altitude_exceeded():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache)
    mission = _load_mission()
    mission.route.waypoints[0].alt_m = 100.0  # max is 30
    result = svc.validate(mission)
    assert not result.passed
    failed = [c for c in result.checks if c.status == CheckStatus.FAILED]
    assert any("altitude" in c.name for c in failed)


def test_point_in_polygon():
    # Simple square: lon [-71.11, -71.09], lat [42.29, 42.31]
    polygon = [[-71.11, 42.29], [-71.09, 42.29], [-71.09, 42.31], [-71.11, 42.31]]
    assert _point_in_polygon(42.30, -71.10, polygon)  # inside
    assert not _point_in_polygon(42.32, -71.10, polygon)  # above
    assert not _point_in_polygon(42.30, -71.12, polygon)  # left
