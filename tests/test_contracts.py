import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from wyvern.contracts import (
    Approval,
    ApprovalStatus,
    Constraints,
    Geofence,
    Mission,
    MissionType,
    Route,
    Waypoint,
)
from wyvern.hashing import hash_model

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_sample_mission():
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    mission = Mission(**data)
    assert mission.mission_id == "mis_test_001"
    assert mission.mission_type == MissionType.POINT_INSPECTION
    assert len(mission.route.waypoints) == 3
    assert mission.approval.status == ApprovalStatus.DRAFT


def test_mission_hash_deterministic():
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    m1 = Mission(**data)
    m2 = Mission(**data)
    assert hash_model(m1) == hash_model(m2)


def test_mission_hash_changes_on_mutation():
    data = json.loads((FIXTURES / "sample_mission.json").read_text())
    m1 = Mission(**data)
    data["mission_id"] = "mis_test_002"
    m2 = Mission(**data)
    assert hash_model(m1) != hash_model(m2)


def test_geofence_min_coordinates():
    with pytest.raises(ValidationError):
        Geofence(type="polygon", coordinates=[[0, 0], [1, 1]])


def test_waypoint_seq_minimum():
    with pytest.raises(ValidationError):
        Waypoint(seq=0, lat=0, lon=0, alt_m=10)


def test_route_requires_at_least_one_waypoint():
    with pytest.raises(ValidationError):
        Route(waypoints=[])


def test_constraints_battery_range():
    with pytest.raises(ValidationError):
        Constraints(
            max_altitude_m=30,
            min_battery_percent=101,
            telemetry_freshness_ms=1500,
            mission_timeout_s=600,
            link_loss_policy="rtl",
            rtl_policy="immediate",
            start_mode="guided",
        )


def test_approval_default_status():
    a = Approval()
    assert a.status == ApprovalStatus.DRAFT
    assert a.approved_by is None
