import asyncio
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api import streams
from api.deps import get_db
from core.errors import NOT_FOUND, AppError
from core.sse import heartbeat, merge_stream, sse_event
from models.analysis import FAILED, SUCCEEDED, BugAnalysis

router = APIRouter(tags=["analysis-stream"])

TERMINAL = {SUCCEEDED, FAILED}


@router.get("/analyses/{analysis_id}/stream")
async def analysis_stream(analysis_id: uuid.UUID, request: Request, db=Depends(get_db)):
    row = db.get(BugAnalysis, analysis_id)
    if row is None:
        raise AppError(NOT_FOUND, "分析任务不存在")
    sid = str(analysis_id)
    snapshot = {"status": row.status, "files": row.located_files or []}

    async def gen():
        yield sse_event("snapshot", snapshot)
        if snapshot["status"] in TERMINAL:
            if snapshot["files"]:
                yield sse_event("located", {"files": snapshot["files"]})
            if snapshot["status"] == SUCCEEDED:
                yield sse_event(
                    "done",
                    {
                        "analysis_id": sid,
                        "status": "succeeded",
                        "patch_applicable": row.patch_applicable,
                    },
                )
            else:
                yield sse_event(
                    "error",
                    {
                        "code": "INTERNAL",
                        "message": row.error_message or "分析失败",
                        "hint": "可补充报错文本与复现步骤",
                    },
                )
                yield sse_event("done", {"analysis_id": sid, "status": "failed"})
            return

        queue = await streams.subscribe(sid)
        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield sse_event(event, data)
                if event in {"done"}:
                    break
        finally:
            streams.unsubscribe(sid)

    return StreamingResponse(
        merge_stream(gen(), heartbeat()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
