from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from wyvern.context import WyvernContext
from wyvern.contracts import (
    ApprovalStatus,
    ChimeraApprovalRequest,
    Mission,
    MissionCommandResult,
    TraceLink,
    ValidationResult,
    WyvernEvent,
)
from wyvern.state_machine import MissionState
from wyvern.store import InvalidTransition


def register(router: APIRouter, ctx: WyvernContext) -> None:
    store = ctx.mission_store
    validation_svc = ctx.validation_service
    executor = ctx.executor
    chimera = ctx.chimera_client
    emitter = ctx.event_emitter

    @router.post("/missions", status_code=201, response_model=Mission)
    async def create_mission(
        payload: Mission,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        if not payload.mission_id or payload.mission_id == "":
            payload.mission_id = f"mis_{uuid.uuid4().hex[:20]}"
        if not payload.trace_id or payload.trace_id == "":
            payload.trace_id = f"trc_{uuid.uuid4().hex[:20]}"

        payload.approval.status = ApprovalStatus.DRAFT

        existing = store.get(payload.mission_id)
        if existing is not None:
            return existing.mission

        store.create(payload)

        await emitter.emit(WyvernEvent(
            event_type="mission.created",
            mission_id=payload.mission_id,
            vehicle_id=payload.vehicle_id,
            trace_id=payload.trace_id,
            timestamp=datetime.now(timezone.utc),
            payload={"mission_type": payload.mission_type.value},
        ))

        return payload

    @router.get("/missions/{mission_id}", response_model=Mission)
    async def get_mission(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return record.mission

    @router.get("/missions/{mission_id}/state")
    async def get_mission_state(mission_id: str):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")
        return {"mission_id": mission_id, "state": record.state.value}

    @router.post("/missions/{mission_id}/validate", response_model=ValidationResult)
    async def validate_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if idempotency_key:
            prev = store.check_idempotency(mission_id, idempotency_key)
            if prev is not None:
                return ValidationResult(**prev)

        result = validation_svc.validate(record.mission)
        store.set_validation(mission_id, result)

        if result.passed:
            try:
                store.transition(
                    mission_id, MissionState.VALIDATED,
                    actor="wyvern_validator", reason_code="mission.validated",
                )
                store.transition(
                    mission_id, MissionState.AWAITING_APPROVAL,
                    actor="wyvern_validator", reason_code="mission.awaiting_approval",
                )
                await emitter.emit(WyvernEvent(
                    event_type="mission.awaiting_approval",
                    mission_id=mission_id,
                    trace_id=record.mission.trace_id,
                    timestamp=datetime.now(timezone.utc),
                ))
            except InvalidTransition:
                pass

        if idempotency_key:
            store.record_idempotency(mission_id, idempotency_key, result.model_dump())

        return result

    @router.post("/missions/{mission_id}/approve", response_model=MissionCommandResult)
    async def approve_mission(
        mission_id: str,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if idempotency_key:
            prev = store.check_idempotency(mission_id, idempotency_key)
            if prev is not None:
                return MissionCommandResult(**prev)

        # Call Chimera for approval
        traceparent = request.headers.get("traceparent")
        chimera_resp = await chimera.request_approval(ChimeraApprovalRequest(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            vehicle_id=record.mission.vehicle_id,
            mission_type=record.mission.mission_type.value,
            requested_by=record.mission.requested_by,
            traceparent=traceparent,
        ))

        # Store trace link
        store.append_trace_link(mission_id, TraceLink(
            wyvern_trace_id=record.mission.trace_id,
            chimera_trace_id=chimera_resp.chimera_trace_id,
            traceparent=traceparent,
            linked_at=datetime.now(timezone.utc),
        ))

        if chimera_resp.status == "rejected":
            try:
                store.transition(
                    mission_id, MissionState.REJECTED,
                    actor="chimera", reason_code=chimera_resp.reason or "chimera.rejected",
                )
            except InvalidTransition as e:
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot reject: current state is {e.from_state.value}",
                )

            await emitter.emit(WyvernEvent(
                event_type="mission.rejected",
                mission_id=mission_id,
                trace_id=record.mission.trace_id,
                timestamp=datetime.now(timezone.utc),
                payload={"reason": chimera_resp.reason},
            ))

            result = MissionCommandResult(
                mission_id=mission_id,
                trace_id=record.mission.trace_id,
                state=MissionState.REJECTED.value,
                reason_code=chimera_resp.reason or "chimera.rejected",
                effective_authority="chimera",
            )
            if idempotency_key:
                store.record_idempotency(mission_id, idempotency_key, result.model_dump())
            return result

        # Chimera approved
        try:
            store.transition(
                mission_id, MissionState.APPROVED,
                actor=f"operator:{chimera_resp.approved_by or 'chimera'}",
                reason_code="mission.approved",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot approve: current state is {e.from_state.value}",
            )

        record.mission.approval.status = ApprovalStatus.APPROVED
        record.mission.approval.approved_by = chimera_resp.approved_by
        record.mission.approval.approved_at = chimera_resp.approved_at or datetime.now(timezone.utc)

        await emitter.emit(WyvernEvent(
            event_type="mission.approved",
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            timestamp=datetime.now(timezone.utc),
            payload={"approved_by": chimera_resp.approved_by},
        ))

        result = MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.APPROVED.value,
            reason_code="mission.approved",
            effective_authority=f"operator:{chimera_resp.approved_by or 'chimera'}",
        )

        if idempotency_key:
            store.record_idempotency(mission_id, idempotency_key, result.model_dump())

        return result

    @router.post("/missions/{mission_id}/execute", response_model=MissionCommandResult)
    async def execute_mission(
        mission_id: str,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        record = store.get(mission_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Mission not found")

        if idempotency_key:
            prev = store.check_idempotency(mission_id, idempotency_key)
            if prev is not None:
                return MissionCommandResult(**prev)

        try:
            store.transition(
                mission_id, MissionState.STAGING,
                actor="wyvern_executor", reason_code="mission.staging",
            )
        except InvalidTransition as e:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot execute: current state is {e.from_state.value}",
            )

        await emitter.emit(WyvernEvent(
            event_type="mission.staging",
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            timestamp=datetime.now(timezone.utc),
        ))

        asyncio.create_task(executor.execute(mission_id))

        result = MissionCommandResult(
            mission_id=mission_id,
            trace_id=record.mission.trace_id,
            state=MissionState.STAGING.value,
            reason_code="mission.staging",
            effective_authority="wyvern_executor",
        )

        if idempotency_key:
            store.record_idempotency(mission_id, idempotency_key, result.model_dump())

        return result
