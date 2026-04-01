import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

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
from wyvern.services.validation import ValidationService
from wyvern.store import VehicleTelemetryCache

FIXTURES = Path(__file__).parent / "fixtures"


def _make_telemetry(vehicle_id: str = "veh_px4_sitl_001") -> TelemetryEvent:
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
            battery_percent=90,
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


def test_remote_id_inactive_fails():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache, compliance_enabled=True)
    mission = _load_mission()
    mission.regulatory.remote_id_status = "inactive"
    result = svc.validate(mission)
    assert not result.passed
    failed = [c for c in result.checks if c.status == CheckStatus.FAILED]
    assert any("remote_id" in c.name for c in failed)


def test_remote_id_active_passes():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache, compliance_enabled=True)
    mission = _load_mission()
    result = svc.validate(mission)
    compliance_checks = [c for c in result.checks if "remote_id" in c.name]
    assert all(c.status == CheckStatus.PASSED for c in compliance_checks)


def test_no_airspace_auth_warns():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache, compliance_enabled=True)
    mission = _load_mission()
    mission.regulatory.airspace_authorization_ref = None
    result = svc.validate(mission)
    warnings = [c for c in result.checks if c.name == "airspace_authorization" and c.status == CheckStatus.WARNING]
    assert len(warnings) == 1


def test_compliance_disabled_skips_checks():
    cache = VehicleTelemetryCache()
    cache.update("veh_px4_sitl_001", _make_telemetry())
    svc = ValidationService(cache, compliance_enabled=False)
    mission = _load_mission()
    mission.regulatory.remote_id_status = "inactive"
    result = svc.validate(mission)
    # Should pass because compliance checks are skipped
    assert result.passed
    compliance_names = [c.name for c in result.checks if "remote_id" in c.name or "airspace" in c.name]
    assert len(compliance_names) == 0
