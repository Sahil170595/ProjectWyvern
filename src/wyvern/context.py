from __future__ import annotations

from dataclasses import dataclass

from wyvern.config import WyvernSettings
from wyvern.services.archive_exporter import ArchiveExporter
from wyvern.services.chimera_client import ChimeraClient
from wyvern.services.event_emitter import EventEmitter
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
    chimera_client: ChimeraClient
    event_emitter: EventEmitter
    archive_exporter: ArchiveExporter
