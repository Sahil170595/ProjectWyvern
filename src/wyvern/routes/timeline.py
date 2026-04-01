from __future__ import annotations

from fastapi import APIRouter, HTTPException

from wyvern.context import WyvernContext
from wyvern.contracts import ReplayArtifact, ReplaySummary, ValidationResult
from wyvern.hashing import hash_model


def register(router: APIRouter, ctx: WyvernContext) -> None:
    store = ctx.mission_store

    @router.get("/missions/{mission_id}/timeline", response_model=ReplayArtifact)
    async def get_timeline(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        mission_h = hash_model(record.mission)
        approval_h = hash_model(record.mission.approval)

        if record.validation_result is not None:
            validation_h = hash_model(record.validation_result)
        else:
            validation_h = "sha256:none"

        operator_interventions = sum(
            1 for e in record.timeline if e.actor.startswith("operator")
        )
        constraint_violations = sum(
            1 for e in record.timeline
            if e.reason_code.startswith("degraded.") or e.reason_code.startswith("blocked.")
        )

        terminal_state = record.state.value

        if record.archive_ref:
            timeline_ref = f"{record.archive_ref}/timeline.jsonl"
            telemetry_ref = f"{record.archive_ref}/telemetry.jsonl"
        else:
            timeline_ref = f"memory://{mission_id}/timeline"
            telemetry_ref = f"memory://{mission_id}/telemetry"

        return ReplayArtifact(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            mission_hash=mission_h,
            approval_hash=approval_h,
            validation_hash=validation_h,
            timeline_ref=timeline_ref,
            telemetry_ref=telemetry_ref,
            summary=ReplaySummary(
                terminal_state=terminal_state,
                operator_interventions=operator_interventions,
                constraint_violations=constraint_violations,
            ),
        )

    @router.get("/missions/{mission_id}/events")
    async def get_mission_events(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return {"mission_id": mission_id, "events": [e.model_dump() for e in record.timeline]}
