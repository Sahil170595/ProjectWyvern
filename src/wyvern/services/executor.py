from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from wyvern.contracts import WyvernEvent
from wyvern.services.safety_guard import SafetyGuard
from wyvern.state_machine import MissionState, is_terminal
from wyvern.store import InvalidTransition, MissionStore
from wyvern.vehicle.adapter import VehicleAdapter

logger = logging.getLogger(__name__)


class MissionExecutor:
    def __init__(
        self,
        adapter: VehicleAdapter,
        store: MissionStore,
        safety_guard: SafetyGuard,
        event_emitter=None,
        archive_exporter=None,
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._safety_guard = safety_guard
        self._emitter = event_emitter
        self._archiver = archive_exporter

    async def _emit(self, event_type: str, mission_id: str, trace_id: str, **extra) -> None:
        if self._emitter is not None:
            await self._emitter.emit(WyvernEvent(
                event_type=event_type,
                mission_id=mission_id,
                trace_id=trace_id,
                timestamp=datetime.now(timezone.utc),
                payload=extra,
            ))

    async def execute(self, mission_id: str) -> None:
        """Run mission from staging through completion. Called as a background task."""
        try:
            await self._execute_inner(mission_id)
        except asyncio.CancelledError:
            logger.warning("Executor cancelled for mission %s", mission_id)
            self._fail_if_not_terminal(mission_id, "executor.cancelled")
            raise
        except Exception:
            logger.exception("Executor crashed for mission %s", mission_id)
            self._fail_if_not_terminal(mission_id, "executor.crashed")

        # Archive on terminal state
        record = self._store.get(mission_id)
        if record and is_terminal(record.state) and self._archiver:
            try:
                ref = await self._archiver.export(record)
                self._store.set_archive_ref(mission_id, ref)
                await self._emit("mission.archived", mission_id, record.mission.trace_id, archive_ref=ref)
            except Exception:
                logger.exception("Archive export failed for %s", mission_id)

    def _fail_if_not_terminal(self, mission_id: str, reason_code: str) -> None:
        record = self._store.get(mission_id)
        if record is not None and not is_terminal(record.state):
            try:
                self._store.transition(
                    mission_id, MissionState.FAILED,
                    actor="wyvern_executor", reason_code=reason_code,
                )
            except InvalidTransition:
                pass

    async def _execute_inner(self, mission_id: str) -> None:
        record = self._store.get(mission_id)
        if record is None:
            logger.error("Mission %s not found", mission_id)
            return

        trace_id = record.mission.trace_id

        # Stage: upload mission to vehicle
        try:
            await self._adapter.upload_mission(record.mission.route.waypoints)
        except Exception as e:
            logger.error("Mission upload failed: %s", e)
            self._fail_if_not_terminal(mission_id, "staging.upload_failed")
            await self._emit("mission.failed", mission_id, trace_id, reason="staging.upload_failed")
            return

        # Transition to executing
        try:
            self._store.transition(
                mission_id, MissionState.EXECUTING,
                actor="wyvern_executor",
                reason_code="mission.executing",
            )
            await self._emit("mission.executing", mission_id, trace_id)
        except InvalidTransition:
            return

        # Arm and start
        try:
            await self._adapter.arm()
            await self._adapter.start_mission()
        except Exception as e:
            logger.error("Mission start failed: %s", e)
            self._fail_if_not_terminal(mission_id, "staging.start_failed")
            await self._emit("mission.failed", mission_id, trace_id, reason="staging.start_failed")
            return

        # Monitor loop
        while True:
            record = self._store.get(mission_id)
            if record is None:
                break

            state = record.state

            if state not in (MissionState.EXECUTING, MissionState.RESUMING):
                logger.info("Executor yielding: mission %s now in %s", mission_id, state.value)
                break

            # Check mission progress
            current, total = await self._adapter.get_mission_progress()
            if total > 0 and current >= total:
                try:
                    self._store.transition(
                        mission_id, MissionState.COMPLETED,
                        actor="wyvern_executor",
                        reason_code="mission.completed",
                    )
                    await self._emit("mission.completed", mission_id, trace_id)
                except InvalidTransition:
                    pass
                break

            # Safety guard -- only act on actionable violations
            violation = self._safety_guard.check(record)
            if violation is not None:
                code = violation.reason_code
                if code.startswith("degraded.") or code.startswith("timeout."):
                    logger.warning("Safety RTL on %s: %s", mission_id, code)
                    try:
                        self._store.transition(
                            mission_id, MissionState.RTL,
                            actor="safety_guard",
                            reason_code=code,
                        )
                        await self._adapter.return_to_launch()
                        await self._emit("mission.rtl", mission_id, trace_id, reason=code)
                    except InvalidTransition:
                        pass
                    break
                else:
                    logger.debug("Safety warning on %s: %s", mission_id, code)

            await asyncio.sleep(0.1)
