import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db
from core.errors import NOT_FOUND, VALIDATION, AppError
from models.conversation import Conversation, Message

router = APIRouter(prefix="/conversations", tags=["conversations"])


class CreateConversation(BaseModel):
    title: str | None = None


class PostMessage(BaseModel):
    content: str = Field(min_length=1)


def _conversation_out(c: Conversation) -> dict:
    return {
        "id": str(c.id),
        "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _message_out(m: Message) -> dict:
    return {
        "id": str(m.id),
        "conversation_id": str(m.conversation_id),
        "role": m.role,
        "content": m.content,
        "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.post("", status_code=201)
def create_conversation(body: CreateConversation, db: Session = Depends(get_db)):
    conv = Conversation(title=(body.title or "").strip() or None)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conversation_out(conv)


@router.get("")
def list_conversations(db: Session = Depends(get_db)):
    rows = db.query(Conversation).order_by(Conversation.updated_at.desc()).limit(100).all()
    return [_conversation_out(c) for c in rows]


def _load(db: Session, conversation_id: uuid.UUID) -> Conversation:
    conv = db.get(Conversation, conversation_id)
    if conv is None:
        raise AppError(NOT_FOUND, "会话不存在")
    return conv


@router.get("/{conversation_id}")
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conv = _load(db, conversation_id)
    out = _conversation_out(conv)
    out["messages"] = [_message_out(m) for m in conv.messages]
    return out


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conv = _load(db, conversation_id)
    db.delete(conv)
    db.commit()


@router.post("/{conversation_id}/messages", status_code=202)
def post_message(conversation_id: uuid.UUID, body: PostMessage, db: Session = Depends(get_db)):
    content = body.content.strip()
    if not content:
        raise AppError(VALIDATION, "消息内容不能为空")
    conv = _load(db, conversation_id)
    msg = Message(conversation_id=conv.id, role="user", content=content)
    db.add(msg)
    if not conv.title:
        conv.title = content[:40]
    db.commit()
    db.refresh(msg)
    return {
        "message_id": str(msg.id),
        "stream_url": f"/api/v1/conversations/{conv.id}/messages/{msg.id}/stream",
    }
