from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from wyvern.contracts import (
    Mission,
    TelemetryEvent,
    TimelineEntry,
    ValidationResult,
)
from wyvern.state_machine import MissionState, can_transition


class InvalidTransition(Exception):
    def __init__(self, mission_id: str, from_state: MissionState, to_state: MissionState):
        self.mission_id = mission_id
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(
            f"Invalid transition {from_state.value} -> {to_state.value} "
            f"for mission {mission_id}"
        )


@dataclass
class MissionRecord:
    mission: Mission
    state: MissionState
    timeline: list[TimelineEntry] = field(default_factory=list)
    telemetry: list[TelemetryEvent] = field(default_factory=list)
    validation_result: ValidationResult | None = None
    idempotency_keys: dict[str, dict] = field(default_factory=dict)


class MissionStore:
    def __init__(self) -> None:
        self._missions: dict[str, MissionRecord] = {}

    def create(self, mission: Mission) -> MissionRecord:
        record = MissionRecord(mission=mission, state=MissionState.DRAFT)
        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            prior_state=None,
            next_state=MissionState.DRAFT.value,
            actor="api",
            trace_id=mission.trace_id,
            reason_code="mission.created",
        )
        record.timeline.append(entry)
        self._missions[mission.mission_id] = record
        return record

    def get(self, mission_id: str) -> MissionRecord | None:
        return self._missions.get(mission_id)

    def transition(
        self,
        mission_id: str,
        new_state: MissionState,
        actor: str,
        reason_code: str,
    ) -> TimelineEntry:
        record = self._missions.get(mission_id)
        if record is None:
            raise KeyError(f"Mission {mission_id} not found")

        if not can_transition(record.state, new_state):
            raise InvalidTransition(mission_id, record.state, new_state)

        entry = TimelineEntry(
            timestamp=datetime.now(timezone.utc),
            prior_state=record.state.value,
            next_state=new_state.value,
            actor=actor,
            trace_id=record.mission.trace_id,
            reason_code=reason_code,
        )
        record.state = new_state
        record.timeline.append(entry)
        return entry

    def append_telemetry(self, mission_id: str, event: TelemetryEvent) -> None:
        record = self._missions.get(mission_id)
        if record is not None:
            record.telemetry.append(event)

    def set_validation(self, mission_id: str, result: ValidationResult) -> None:
        record = self._missions.get(mission_id)
        if record is not None:
            record.validation_result = result

    def check_idempotency(self, mission_id: str, key: str) -> dict | None:
        """Return previous result if key was already used, else None."""
        record = self._missions.get(mission_id)
        if record is None:
            return None
        return record.idempotency_keys.get(key)

    def record_idempotency(self, mission_id: str, key: str, result: dict) -> None:
        record = self._missions.get(mission_id)
        if record is not None:
            record.idempotency_keys[key] = result

    def get_active_for_vehicle(self, vehicle_id: str) -> MissionRecord | None:
        """Return the currently executing mission for a vehicle, if any."""
        for record in self._missions.values():
            if (
                record.mission.vehicle_id == vehicle_id
                and record.state
                in (MissionState.STAGING, MissionState.EXECUTING, MissionState.RESUMING)
            ):
                return record
        return None


class VehicleTelemetryCache:
    def __init__(self) -> None:
        self._latest: dict[str, TelemetryEvent] = {}

    def update(self, vehicle_id: str, event: TelemetryEvent) -> None:
        self._latest[vehicle_id] = event

    def get(self, vehicle_id: str) -> TelemetryEvent | None:
        return self._latest.get(vehicle_id)
