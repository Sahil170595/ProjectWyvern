from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from wyvern.context import WyvernContext
from wyvern.contracts import MissionCommandResult
from wyvern.state_machine import MissionState
from wyvern.store import InvalidTransition

logger = logging.getLogger(__name__)


def register(router: APIRouter, ctx: WyvernContext) -> None:
    store = ctx.mission_store
    adapter = ctx.vehicle_adapter

    @router.post("/missions/{mission_id}/pause", response_model=MissionCommandResult)
    async def pause_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if record.state == MissionState.PAUSED:
            return MissionCommandResult(
                mission_id=mission_id,
                trace_id=record.mission.trace_id,
                state=MissionState.PAUSED.value,
                reason_code="idempotent.pause_duplicate",
                effective_authority="operator",
            )

        try:
            store.transition(
                mission_id, MissionState.PAUSED,
                actor="operator", reason_code="operator.pause",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot pause: current state is {e.from_state.value}",
            )

        try:
            await adapter.pause_mission()
        except Exception:
            logger.exception("Adapter pause_mission failed for %s (state already PAUSED)", mission_id)

        return MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.PAUSED.value,
            reason_code="operator.pause",
            effective_authority="operator",
        )

    @router.post("/missions/{mission_id}/resume", response_model=MissionCommandResult)
    async def resume_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        try:
            store.transition(
                mission_id, MissionState.RESUMING,
                actor="operator", reason_code="operator.resume",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot resume: current state is {e.from_state.value}",
            )

        try:
            await adapter.start_mission()
            store.transition(
                mission_id, MissionState.EXECUTING,
                actor="wyvern_executor", reason_code="mission.resumed",
            )
        except Exception:
            logger.exception("Resume failed for %s, reverting to PAUSED", mission_id)
            # Revert: RESUMING can't go back to PAUSED directly, so fail it
            try:
                store.transition(
                    mission_id, MissionState.EXECUTING,
                    actor="wyvern_executor", reason_code="mission.resumed",
                )
                store.transition(
                    mission_id, MissionState.FAILED,
                    actor="wyvern_executor", reason_code="resume.adapter_failed",
                )
            except InvalidTransition:
                pass
            raise HTTPException(status_code=500, detail="Vehicle resume failed")

        return MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.EXECUTING.value,
            reason_code="mission.resumed",
            effective_authority="operator",
        )

    @router.post("/missions/{mission_id}/rtl", response_model=MissionCommandResult)
    async def rtl_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if record.state == MissionState.RTL:
            return MissionCommandResult(
                mission_id=mission_id,
                trace_id=record.mission.trace_id,
                state=MissionState.RTL.value,
                reason_code="idempotent.rtl_duplicate",
                effective_authority="operator",
            )

        try:
            store.transition(
                mission_id, MissionState.RTL,
                actor="operator", reason_code="operator.rtl",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot RTL: current state is {e.from_state.value}",
            )

        try:
            await adapter.return_to_launch()
        except Exception:
            logger.exception("Adapter RTL failed for %s (state already RTL)", mission_id)

        return MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.RTL.value,
            reason_code="operator.rtl",
            effective_authority="operator",
        )

    @router.post("/missions/{mission_id}/abort", response_model=MissionCommandResult)
    async def abort_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if record.state == MissionState.ABORTED:
            return MissionCommandResult(
                mission_id=mission_id,
                trace_id=record.mission.trace_id,
                state=MissionState.ABORTED.value,
                reason_code="idempotent.abort_duplicate",
                effective_authority="operator",
            )

        try:
            store.transition(
                mission_id, MissionState.ABORTED,
                actor="operator", reason_code="operator.abort",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot abort: current state is {e.from_state.value}",
            )

        try:
            await adapter.land()
        except Exception:
            logger.exception("Adapter land failed for %s (state already ABORTED)", mission_id)

        return MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.ABORTED.value,
            reason_code="operator.abort",
            effective_authority="operator",
        )
