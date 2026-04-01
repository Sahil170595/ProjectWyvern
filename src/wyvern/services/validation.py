from __future__ import annotations

from datetime import datetime, timezone

from wyvern.contracts import (
    CheckStatus,
    Mission,
    RemoteIdStatus,
    TelemetryEvent,
    ValidationCheck,
    ValidationResult,
)
from wyvern.store import VehicleTelemetryCache


def _point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """Ray-casting point-in-polygon test. Polygon coords are [lon, lat] pairs."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i][0], polygon[i][1]  # lon, lat
        xj, yj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


class ValidationService:
    def __init__(self, telemetry_cache: VehicleTelemetryCache, compliance_enabled: bool = True) -> None:
        self._telemetry_cache = telemetry_cache
        self._compliance_enabled = compliance_enabled

    def validate(self, mission: Mission) -> ValidationResult:
        checks: list[ValidationCheck] = []

        # 1. Geofence containment
        for wp in mission.route.waypoints:
            if not _point_in_polygon(wp.lat, wp.lon, mission.geofence.coordinates):
                checks.append(ValidationCheck(
                    name="geofence_containment",
                    status=CheckStatus.FAILED,
                    reason_code=f"waypoint_seq_{wp.seq}_outside_geofence",
                ))
                break
        else:
            checks.append(ValidationCheck(
                name="geofence_containment",
                status=CheckStatus.PASSED,
            ))

        # 2. Altitude check
        max_alt = mission.constraints.max_altitude_m
        over = [wp for wp in mission.route.waypoints if wp.alt_m > max_alt]
        if over:
            checks.append(ValidationCheck(
                name="altitude_limit",
                status=CheckStatus.FAILED,
                reason_code=f"waypoint_seq_{over[0].seq}_exceeds_{max_alt}m",
            ))
        else:
            checks.append(ValidationCheck(
                name="altitude_limit",
                status=CheckStatus.PASSED,
            ))

        # 3. Battery threshold (from live telemetry)
        telemetry = self._telemetry_cache.get(mission.vehicle_id)
        if telemetry is None:
            checks.append(ValidationCheck(
                name="battery_threshold",
                status=CheckStatus.WARNING,
                reason_code="no_telemetry_available",
            ))
        elif telemetry.health.battery_percent < mission.constraints.min_battery_percent:
            checks.append(ValidationCheck(
                name="battery_threshold",
                status=CheckStatus.FAILED,
                reason_code=f"battery_{telemetry.health.battery_percent:.0f}_below_{mission.constraints.min_battery_percent:.0f}",
            ))
        else:
            checks.append(ValidationCheck(
                name="battery_threshold",
                status=CheckStatus.PASSED,
            ))

        # 4. Telemetry freshness
        if telemetry is None:
            checks.append(ValidationCheck(
                name="telemetry_freshness",
                status=CheckStatus.WARNING,
                reason_code="no_telemetry_available",
            ))
        else:
            age_ms = int(
                (datetime.now(timezone.utc) - telemetry.timestamp).total_seconds() * 1000
            )
            if age_ms > mission.constraints.telemetry_freshness_ms:
                checks.append(ValidationCheck(
                    name="telemetry_freshness",
                    status=CheckStatus.FAILED,
                    reason_code=f"telemetry_age_{age_ms}ms_exceeds_{mission.constraints.telemetry_freshness_ms}ms",
                ))
            else:
                checks.append(ValidationCheck(
                    name="telemetry_freshness",
                    status=CheckStatus.PASSED,
                ))

        # 5. Compliance: Remote ID
        if self._compliance_enabled:
            if mission.regulatory.remote_id_required:
                if mission.regulatory.remote_id_status != RemoteIdStatus.ACTIVE:
                    checks.append(ValidationCheck(
                        name="remote_id_compliance",
                        status=CheckStatus.FAILED,
                        reason_code=f"remote_id_{mission.regulatory.remote_id_status}",
                    ))
                else:
                    checks.append(ValidationCheck(
                        name="remote_id_compliance",
                        status=CheckStatus.PASSED,
                    ))

            # 6. Compliance: Airspace authorization
            if mission.regulatory.operation_type in ("part107", "part107_waiver"):
                if not mission.regulatory.airspace_authorization_ref:
                    checks.append(ValidationCheck(
                        name="airspace_authorization",
                        status=CheckStatus.WARNING,
                        reason_code="no_airspace_auth_ref",
                    ))
                else:
                    checks.append(ValidationCheck(
                        name="airspace_authorization",
                        status=CheckStatus.PASSED,
                    ))

        passed = all(c.status != CheckStatus.FAILED for c in checks)

        return ValidationResult(
            mission_id=mission.mission_id,
            trace_id=mission.trace_id,
            passed=passed,
            checks=checks,
        )
