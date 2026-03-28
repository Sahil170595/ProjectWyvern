from __future__ import annotations

from fastapi import APIRouter

from wyvern.context import WyvernContext


def register_all(router: APIRouter, ctx: WyvernContext) -> None:
    from wyvern.routes import commands, health, missions, timeline, vehicles

    missions.register(router, ctx)
    commands.register(router, ctx)
    timeline.register(router, ctx)
    vehicles.register(router, ctx)
    health.register(router, ctx)
