from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wyvern.context import WyvernContext
from wyvern.contracts import ControlRoomVehiclePanel


def register(router: APIRouter, ctx: WyvernContext) -> None:
    store = ctx.mission_store
    cache = ctx.telemetry_cache

    @router.get("/control-room/vehicles/{vehicle_id}/panel", response_model=ControlRoomVehiclePanel)
    async def vehicle_panel(vehicle_id: str):
        telemetry = cache.get(vehicle_id)
        active = store.get_active_for_vehicle(vehicle_id)
        return ControlRoomVehiclePanel(
            vehicle_id=vehicle_id,
            vehicle_state=telemetry.vehicle_state if telemetry else None,
            position=telemetry.position if telemetry else None,
            health=telemetry.health if telemetry else None,
            active_mission_id=active.mission.mission_id if active else None,
            mission_state=active.state.value if active else None,
            last_telemetry_at=telemetry.timestamp if telemetry else None,
        )

    @router.get("/control-room/fleet")
    async def fleet_status():
        missions = store.list_missions()
        vehicles: dict[str, dict] = {}
        for record in missions:
            vid = record.mission.vehicle_id
            if vid not in vehicles or record.state.value in (
                "staging", "executing", "paused", "resuming", "rtl",
            ):
                vehicles[vid] = {
                    "vehicle_id": vid,
                    "latest_mission_id": record.mission.mission_id,
                    "latest_state": record.state.value,
                }
        return {"vehicles": list(vehicles.values())}

    @router.get("/control-room/missions/{mission_id}/state")
    async def mission_full_state(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return {
            "mission_id": mission_id,
            "state": record.state.value,
            "trace_links": [tl.model_dump(mode="json") for tl in record.trace_links],
            "incident_count": len(record.incidents),
            "timeline_entries": len(record.timeline),
            "telemetry_points": len(record.telemetry),
            "archive_ref": record.archive_ref,
        }

    @router.get("/control-room/missions/{mission_id}/incidents")
    async def mission_incidents(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return {
            "mission_id": mission_id,
            "incidents": [i.model_dump(mode="json") for i in record.incidents],
        }
