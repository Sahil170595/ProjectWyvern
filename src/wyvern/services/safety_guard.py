from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from wyvern.contracts import TelemetryEvent
from wyvern.store import MissionRecord, VehicleTelemetryCache


@dataclass
class SafetyViolation:
    reason_code: str
    message: str


class SafetyGuard:
    def __init__(self, telemetry_cache: VehicleTelemetryCache) -> None:
        self._telemetry_cache = telemetry_cache

    def check(self, record: MissionRecord) -> SafetyViolation | None:
        """Run runtime safety checks. Returns first violation found, or None."""
        mission = record.mission
        telemetry = self._telemetry_cache.get(mission.vehicle_id)

        if telemetry is None:
            return SafetyViolation(
                reason_code="blocked.no_telemetry",
                message="No telemetry available for vehicle",
            )

        # Battery floor
        if telemetry.health.battery_percent < mission.constraints.min_battery_percent:
            return SafetyViolation(
                reason_code="degraded.battery_low",
                message=f"Battery {telemetry.health.battery_percent:.0f}% below minimum {mission.constraints.min_battery_percent:.0f}%",
            )

        # Link quality
        if telemetry.health.link_quality < 0.3:
            return SafetyViolation(
                reason_code="degraded.link_quality",
                message=f"Link quality {telemetry.health.link_quality:.2f} below 0.3 threshold",
            )

        # Estimator health
        if telemetry.health.estimator_status not in ("nominal", "good", "ok"):
            return SafetyViolation(
                reason_code="degraded.estimator",
                message=f"Estimator status: {telemetry.health.estimator_status}",
            )

        # Telemetry freshness
        age_ms = int(
            (datetime.now(timezone.utc) - telemetry.timestamp).total_seconds() * 1000
        )
        if age_ms > mission.constraints.telemetry_freshness_ms:
            return SafetyViolation(
                reason_code="blocked.telemetry_stale",
                message=f"Telemetry age {age_ms}ms exceeds {mission.constraints.telemetry_freshness_ms}ms",
            )

        # Mission timeout
        staging_entry = next(
            (e for e in record.timeline if e.next_state == "staging"),
            None,
        )
        if staging_entry is not None:
            elapsed_s = (datetime.now(timezone.utc) - staging_entry.timestamp).total_seconds()
            if elapsed_s > mission.constraints.mission_timeout_s:
                return SafetyViolation(
                    reason_code="timeout.mission",
                    message=f"Mission elapsed {elapsed_s:.0f}s exceeds timeout {mission.constraints.mission_timeout_s}s",
                )

        return None
