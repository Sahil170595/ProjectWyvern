from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from wyvern.contracts import MissionProgress, TelemetryEvent, VehicleState
from wyvern.store import MissionStore, VehicleTelemetryCache
from wyvern.vehicle.adapter import VehicleAdapter

logger = logging.getLogger(__name__)


class TelemetryCollector:
    def __init__(
        self,
        adapter: VehicleAdapter,
        telemetry_cache: VehicleTelemetryCache,
        mission_store: MissionStore,
        interval_ms: int = 500,
    ) -> None:
        self._adapter = adapter
        self._cache = telemetry_cache
        self._store = mission_store
        self._interval_s = interval_ms / 1000.0
        self._stop = asyncio.Event()

    async def run(self) -> None:
        while not self._stop.is_set():
            try:
                event = await self._collect_one()
                self._cache.update(self._adapter.vehicle_id, event)

                active = self._store.get_active_for_vehicle(self._adapter.vehicle_id)
                if active is not None:
                    self._store.append_telemetry(active.mission.mission_id, event)
            except Exception:
                logger.exception("Telemetry collection error")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._interval_s)
                break  # stop was set
            except asyncio.TimeoutError:
                pass  # normal loop

    def stop(self) -> None:
        self._stop.set()

    async def _collect_one(self) -> TelemetryEvent:
        position = await self._adapter.get_position()
        velocity = await self._adapter.get_velocity()
        health = await self._adapter.get_health()
        armed = await self._adapter.is_armed()
        in_air = await self._adapter.is_in_air()
        flight_mode = await self._adapter.get_flight_mode()
        current_wp, total_wp = await self._adapter.get_mission_progress()

        active = self._store.get_active_for_vehicle(self._adapter.vehicle_id)
        mission_id = active.mission.mission_id if active else ""
        trace_id = active.mission.trace_id if active else ""

        return TelemetryEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            trace_id=trace_id,
            mission_id=mission_id,
            vehicle_id=self._adapter.vehicle_id,
            timestamp=datetime.now(timezone.utc),
            vehicle_state=VehicleState(mode=flight_mode, armed=armed, in_air=in_air),
            position=position,
            velocity=velocity,
            health=health,
            mission_progress=MissionProgress(
                state=flight_mode,
                current_waypoint=current_wp,
                waypoints_total=total_wp,
            ),
        )
