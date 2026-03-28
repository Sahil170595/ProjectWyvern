from __future__ import annotations

from fastapi import APIRouter

from wyvern.context import WyvernContext


def register(router: APIRouter, ctx: WyvernContext) -> None:

    @router.get("/health")
    async def health_check():
        return {"status": "ok"}

    @router.get("/ready")
    async def readiness_check():
        connected = await ctx.vehicle_adapter.is_connected()
        return {"ready": connected}
