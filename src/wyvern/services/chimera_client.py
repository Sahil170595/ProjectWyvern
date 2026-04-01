from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from wyvern.contracts import ChimeraApprovalRequest, ChimeraApprovalResponse

logger = logging.getLogger(__name__)


@runtime_checkable
class ChimeraClient(Protocol):
    async def request_approval(
        self, request: ChimeraApprovalRequest
    ) -> ChimeraApprovalResponse: ...

    async def notify_mission_event(
        self,
        event_type: str,
        mission_id: str,
        trace_id: str,
        payload: dict[str, Any],
    ) -> None: ...


class MockChimeraClient:
    """Mock Chimera client for testing. Auto-approves by default."""

    def __init__(self, *, auto_approve: bool = True) -> None:
        self._auto_approve = auto_approve
        self._rejection_reason: str | None = None
        self._approvals: dict[str, ChimeraApprovalResponse] = {}
        self._events: list[dict[str, Any]] = []

    def set_auto_approve(self, value: bool) -> None:
        self._auto_approve = value

    def set_rejection_reason(self, reason: str) -> None:
        self._auto_approve = False
        self._rejection_reason = reason

    def get_events(self) -> list[dict[str, Any]]:
        return list(self._events)

    async def request_approval(
        self, request: ChimeraApprovalRequest
    ) -> ChimeraApprovalResponse:
        approval_id = f"apr_{uuid.uuid4().hex[:12]}"
        chimera_trace_id = f"ctrc_{uuid.uuid4().hex[:12]}"

        if self._auto_approve:
            resp = ChimeraApprovalResponse(
                approval_id=approval_id,
                status="approved",
                approved_by=f"mock_operator_{request.requested_by.principal_id}",
                approved_at=datetime.now(timezone.utc),
                chimera_trace_id=chimera_trace_id,
            )
        else:
            resp = ChimeraApprovalResponse(
                approval_id=approval_id,
                status="rejected",
                reason=self._rejection_reason or "mock_rejection",
                chimera_trace_id=chimera_trace_id,
            )

        self._approvals[approval_id] = resp
        return resp

    async def notify_mission_event(
        self,
        event_type: str,
        mission_id: str,
        trace_id: str,
        payload: dict[str, Any],
    ) -> None:
        self._events.append({
            "event_type": event_type,
            "mission_id": mission_id,
            "trace_id": trace_id,
            "payload": payload,
        })


class HttpChimeraClient:
    """Real HTTP client for Chimera/JARVIS integration."""

    def __init__(self, *, url: str, timeout: float = 5.0) -> None:
        self._url = url.rstrip("/")
        self._timeout = timeout

    async def request_approval(
        self, request: ChimeraApprovalRequest
    ) -> ChimeraApprovalResponse:
        import httpx

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if request.traceparent:
            headers["traceparent"] = request.traceparent

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._url}/wyvern/approvals",
                json=request.model_dump(mode="json"),
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return ChimeraApprovalResponse(**data)

    async def notify_mission_event(
        self,
        event_type: str,
        mission_id: str,
        trace_id: str,
        payload: dict[str, Any],
    ) -> None:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                await client.post(
                    f"{self._url}/wyvern/events",
                    json={
                        "event_type": event_type,
                        "mission_id": mission_id,
                        "trace_id": trace_id,
                        "payload": payload,
                    },
                )
        except Exception:
            logger.debug("Failed to notify Chimera event %s", event_type, exc_info=True)
