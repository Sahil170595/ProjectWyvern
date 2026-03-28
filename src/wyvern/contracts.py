from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- Enums ---

class MissionType(str, Enum):
    TAKEOFF_LAND = "takeoff_land"
    WAYPOINT_PATROL = "waypoint_patrol"
    POINT_INSPECTION = "point_inspection"
    ROUTE_FOLLOW = "route_follow"
    ORBIT_TARGET = "orbit_target"
    RETURN_TO_LAUNCH = "return_to_launch"
    AREA_SURVEY = "area_survey"
    ASSET_INSPECTION = "asset_inspection"
    DOCK_DEPART = "dock_depart"
    DOCK_RETURN = "dock_return"
    ESCORT_FOLLOW = "escort_follow"
    MULTI_VEHICLE_SWEEP = "multi_vehicle_sweep"


class AutonomyLevel(str, Enum):
    L0_MANUAL = "L0_manual"
    L1_ASSISTED = "L1_assisted"
    L2_SUPERVISED = "L2_supervised"
    L3_COORDINATED = "L3_coordinated"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class LinkLossPolicy(str, Enum):
    HOLD = "hold"
    RTL = "rtl"
    LAND = "land"


class RemoteIdStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNKNOWN = "unknown"


class CheckStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"


# --- Mission sub-models ---

class RequestedBy(BaseModel):
    principal_id: str
    role: str


class Approval(BaseModel):
    status: ApprovalStatus = ApprovalStatus.DRAFT
    approved_by: str | None = None
    approved_at: datetime | None = None


class Geofence(BaseModel):
    type: str = "polygon"
    coordinates: list[list[float]] = Field(min_length=3)


class Waypoint(BaseModel):
    seq: int = Field(ge=1)
    lat: float
    lon: float
    alt_m: float
    hold_s: int = Field(default=0, ge=0)


class Route(BaseModel):
    waypoints: list[Waypoint] = Field(min_length=1)


class Constraints(BaseModel):
    max_altitude_m: float
    min_battery_percent: float = Field(ge=0, le=100)
    telemetry_freshness_ms: int = Field(ge=1)
    mission_timeout_s: int = Field(ge=1)
    link_loss_policy: LinkLossPolicy
    rtl_policy: str
    start_mode: str


class Regulatory(BaseModel):
    operation_type: str
    remote_id_required: bool
    remote_id_status: RemoteIdStatus
    airspace_authorization_ref: str | None = None
    observer_required: bool


# --- Mission ---

class Mission(BaseModel):
    schema_version: str = "wyvern.mission.v1"
    mission_id: str
    trace_id: str
    vehicle_id: str
    mission_type: MissionType
    autonomy_level: AutonomyLevel
    requested_by: RequestedBy
    approval: Approval
    geofence: Geofence
    route: Route
    constraints: Constraints
    regulatory: Regulatory
    payload: dict[str, Any] | None = None
    risk: dict[str, Any] | None = None
    created_at: datetime


# --- Telemetry ---

class VehicleState(BaseModel):
    mode: str
    armed: bool
    in_air: bool


class Position(BaseModel):
    lat: float
    lon: float
    alt_m: float


class Velocity(BaseModel):
    ground_speed_mps: float
    vertical_speed_mps: float


class Health(BaseModel):
    battery_percent: float = Field(ge=0, le=100)
    gps_fix: str
    telemetry_age_ms: int = Field(ge=0)
    link_quality: float = Field(ge=0, le=1)
    estimator_status: str


class MissionProgress(BaseModel):
    state: str
    current_waypoint: int = Field(ge=0)
    waypoints_total: int = Field(ge=0)


class TelemetryEvent(BaseModel):
    schema_version: str = "wyvern.telemetry.v1"
    event_id: str
    trace_id: str
    mission_id: str
    vehicle_id: str
    timestamp: datetime
    vehicle_state: VehicleState
    position: Position
    velocity: Velocity
    health: Health
    mission_progress: MissionProgress


# --- Replay ---

class ReplaySummary(BaseModel):
    terminal_state: str
    operator_interventions: int = Field(ge=0)
    constraint_violations: int = Field(ge=0)


class ReplayArtifact(BaseModel):
    schema_version: str = "wyvern.replay.v1"
    mission_id: str
    trace_id: str
    mission_hash: str
    approval_hash: str
    validation_hash: str
    timeline_ref: str
    telemetry_ref: str
    summary: ReplaySummary


# --- API responses ---

class MissionCommandResult(BaseModel):
    mission_id: str
    trace_id: str
    state: str
    reason_code: str
    effective_authority: str | None = None


class ValidationCheck(BaseModel):
    name: str
    status: CheckStatus
    reason_code: str | None = None


class ValidationResult(BaseModel):
    mission_id: str
    trace_id: str
    passed: bool
    checks: list[ValidationCheck]


class ErrorResponse(BaseModel):
    error: str
    reason_code: str
    trace_id: str
    mission_id: str | None = None
    vehicle_id: str | None = None


# --- Timeline ---

class TimelineEntry(BaseModel):
    timestamp: datetime
    prior_state: str | None
    next_state: str
    actor: str
    trace_id: str
    reason_code: str
