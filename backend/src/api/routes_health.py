from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.deps import get_db, get_llm, get_rag
from llm.client import LLMClient
from rag.clients import RAG

router = APIRouter(tags=["health"])


def _mysql_ok(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


@router.get("/health")
async def health(
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    rag: RAG = Depends(get_rag),
):
    mysql = "ok" if _mysql_ok(db) else "degraded"
    rag_status = rag.health()
    llm_status = "ok" if await llm.ping() else "degraded"
    components = [
        mysql,
        llm_status,
        rag_status["milvus"],
        rag_status["neo4j"],
        rag_status["minio"],
    ]
    overall = "ok" if all(v == "ok" for v in components) else "degraded"
    return {
        "status": overall,
        "mysql": mysql,
        "milvus": rag_status["milvus"],
        "neo4j": rag_status["neo4j"],
        "minio": rag_status["minio"],
        "llm": llm_status,
    }
