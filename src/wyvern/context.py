from __future__ import annotations

from dataclasses import dataclass

from wyvern.config import WyvernSettings
from wyvern.services.executor import MissionExecutor
from wyvern.services.safety_guard import SafetyGuard
from wyvern.services.validation import ValidationService
from wyvern.store import MissionStore, VehicleTelemetryCache
from wyvern.vehicle.adapter import VehicleAdapter


@dataclass(frozen=True)
class WyvernContext:
    settings: WyvernSettings
    mission_store: MissionStore
    telemetry_cache: VehicleTelemetryCache
    vehicle_adapter: VehicleAdapter
    validation_service: ValidationService
    executor: MissionExecutor
    safety_guard: SafetyGuard
