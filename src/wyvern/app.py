from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from wyvern.config import WyvernSettings
from wyvern.context import WyvernContext
from wyvern.routes import register_all
from wyvern.services.archive_exporter import ArchiveExporter
from wyvern.services.chimera_client import MockChimeraClient
from wyvern.services.event_emitter import EventEmitter
from wyvern.services.executor import MissionExecutor
from wyvern.services.safety_guard import SafetyGuard
from wyvern.services.validation import ValidationService
from wyvern.store import MissionStore, VehicleTelemetryCache
from wyvern.vehicle.mock_adapter import MockVehicleAdapter
from wyvern.vehicle.telemetry_collector import TelemetryCollector


def _build_context(settings: WyvernSettings | None = None) -> WyvernContext:
    if settings is None:
        settings = WyvernSettings()

    mission_store = MissionStore()
    telemetry_cache = VehicleTelemetryCache()

    if settings.use_mock_vehicle:
        adapter = MockVehicleAdapter(vehicle_id=settings.vehicle_id)
    else:
        from wyvern.vehicle.mavsdk_adapter import MavsdkVehicleAdapter

        adapter = MavsdkVehicleAdapter(
            system_address=settings.vehicle_address,
            vehicle_id=settings.vehicle_id,
        )

    validation_service = ValidationService(
        telemetry_cache=telemetry_cache,
        compliance_enabled=settings.compliance_enabled,
    )
    safety_guard = SafetyGuard(telemetry_cache=telemetry_cache)
    event_emitter = EventEmitter(buffer_size=settings.ws_event_buffer_size)
    archive_exporter = ArchiveExporter(archive_dir=settings.archive_dir)

    if settings.chimera_url:
        from wyvern.services.chimera_client import HttpChimeraClient

        chimera_client = HttpChimeraClient(
            url=settings.chimera_url, timeout=settings.chimera_timeout_s
        )
    else:
        chimera_client = MockChimeraClient()

    executor_svc = MissionExecutor(
        adapter=adapter,
        store=mission_store,
        safety_guard=safety_guard,
        event_emitter=event_emitter,
        archive_exporter=archive_exporter if settings.archive_on_completion else None,
    )

    return WyvernContext(
        settings=settings,
        mission_store=mission_store,
        telemetry_cache=telemetry_cache,
        vehicle_adapter=adapter,
        validation_service=validation_service,
        executor=executor_svc,
        safety_guard=safety_guard,
        chimera_client=chimera_client,
        event_emitter=event_emitter,
        archive_exporter=archive_exporter,
    )


def create_app(settings: WyvernSettings | None = None) -> FastAPI:
    ctx = _build_context(settings)

    collector = TelemetryCollector(
        adapter=ctx.vehicle_adapter,
        telemetry_cache=ctx.telemetry_cache,
        mission_store=ctx.mission_store,
        interval_ms=ctx.settings.telemetry_interval_ms,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await ctx.vehicle_adapter.connect()
        telemetry_task = asyncio.create_task(collector.run())
        yield
        collector.stop()
        telemetry_task.cancel()
        try:
            await telemetry_task
        except asyncio.CancelledError:
            pass

    app = FastAPI(
        title="ChimeraWyvern API",
        version="2.0.0",
        lifespan=lifespan,
    )

    router = APIRouter(prefix="/api/v1")
    register_all(router, ctx)
    app.include_router(router)

    return app
