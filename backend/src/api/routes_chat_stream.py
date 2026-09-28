import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from api.deps import get_llm, get_rag
from core.db import SessionLocal
from core.errors import NOT_FOUND, AppError
from core.sse import heartbeat, merge_stream, sse_event
from llm.client import LLMClient
from models.conversation import Conversation, Message
from rag.clients import RAG
from services.chat_service import stream_reply

router = APIRouter(tags=["chat-stream"])


@router.get("/conversations/{conversation_id}/messages/{message_id}/stream")
async def chat_stream(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    request: Request,
    llm: LLMClient = Depends(get_llm),
    rag: RAG = Depends(get_rag),
):
    def load() -> tuple[list[dict], str]:
        db = SessionLocal()
        try:
            conv = db.get(Conversation, conversation_id)
            msg = db.get(Message, message_id)
            if conv is None or msg is None or msg.conversation_id != conv.id:
                raise AppError(NOT_FOUND, "会话或消息不存在")
            history = [
                {"role": m.role, "content": m.content}
                for m in conv.messages
                if m.id != msg.id
            ]
            return history, msg.content
        finally:
            db.close()

    history, user_text = load()

    async def gen():
        parts: list[str] = []
        sources: list[dict] = []
        persisted = False

        def persist() -> None:
            nonlocal persisted
            if persisted or not parts:
                return
            db = SessionLocal()
            try:
                db.add(
                    Message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content="".join(parts),
                        meta={"sources": sources} if sources else None,
                    )
                )
                conv = db.get(Conversation, conversation_id)
                if conv is not None:
                    from datetime import datetime

                    conv.updated_at = datetime.utcnow()
                db.commit()
            finally:
                db.close()
            persisted = True

        try:
            async for ev in stream_reply(llm, user_text, history, rag_store=rag):
                if ev["event"] == "delta":
                    parts.append(ev["data"]["text"])
                elif ev["event"] == "sources":
                    sources = ev["data"]["items"]
                if ev["event"] == "error":
                    yield sse_event("error", ev["data"])
                    return
                if ev["event"] == "done":
                    persist()
                yield sse_event(ev["event"], ev["data"])
        finally:
            persist()

    return StreamingResponse(
        merge_stream(gen(), heartbeat()),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
