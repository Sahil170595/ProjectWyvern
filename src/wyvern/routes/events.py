from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from wyvern.context import WyvernContext


def register(router: APIRouter, ctx: WyvernContext) -> None:
    emitter = ctx.event_emitter

    @router.websocket("/events")
    async def event_stream(websocket: WebSocket):
        await websocket.accept()
        since_seq = int(websocket.query_params.get("since_seq", "0"))
        queue = emitter.subscribe()
        try:
            for event in emitter.recent_events(since_seq):
                await websocket.send_json(event.model_dump(mode="json"))
            while True:
                event = await queue.get()
                await websocket.send_json(event.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            emitter.unsubscribe(queue)
