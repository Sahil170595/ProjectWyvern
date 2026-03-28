from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wyvern.context import WyvernContext
from wyvern.contracts import TelemetryEvent


def register(router: APIRouter, ctx: WyvernContext) -> None:
    cache = ctx.telemetry_cache

    @router.get("/vehicles/{vehicle_id}/telemetry", response_model=TelemetryEvent)
    async def get_vehicle_telemetry(vehicle_id: str):
        event = cache.get(vehicle_id)
        if event is None:
            raise HTTPException(status_code=404, detail="No telemetry for vehicle")
        return event
