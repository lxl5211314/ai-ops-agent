import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from api.deps import get_db, get_llm, get_rag
from core.errors import NOT_FOUND, UNPROCESSABLE, VALIDATION, AppError
from llm.client import LLMClient
from models.kb import KbDocument, KbIngestJob
from rag.clients import RAG
from rag.ingest import guess_content_type, new_object_key

router = APIRouter(prefix="/kb", tags=["kb"])

ALLOWED_CATEGORIES = {"enterprise_background", "ops_knowledge"}
MAX_DOC_BYTES = 20 * 1024 * 1024


def _doc_out(doc: KbDocument, job: KbIngestJob | None = None) -> dict:
    return {
        "id": str(doc.id),
        "title": doc.title,
        "category": doc.category,
        "chunk_count": doc.chunk_count,
        "graph_node_count": doc.graph_node_count,
        "status": doc.status,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "job": {"stage": job.stage, "detail": job.detail} if job else None,
    }


@router.post("/documents", status_code=202)
async def upload_document(
    background: BackgroundTasks,
    category: str = Form(...),
    title: str = Form(""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    llm: LLMClient = Depends(get_llm),
    rag: RAG = Depends(get_rag),
):
    if category not in ALLOWED_CATEGORIES:
        raise AppError(VALIDATION, "category 必须是 enterprise_background 或 ops_knowledge")
    data = await file.read()
    if not data:
        raise AppError(VALIDATION, "文件内容为空")
    if len(data) > MAX_DOC_BYTES:
        raise AppError(UNPROCESSABLE, "文件超过 20MB 上限")
    filename = file.filename or "document.txt"
    object_key = new_object_key(filename)
    try:
        rag.minio.put(rag.bucket_docs, object_key, data, guess_content_type(filename))
    except Exception as exc:  # noqa: BLE001
        raise AppError(
            UNPROCESSABLE, "对象存储不可用，文档保存失败", {"detail": str(exc)}
        ) from exc

    doc = KbDocument(
        title=(title.strip() or filename)[:200],
        category=category,
        object_key=object_key,
        status="PENDING",
    )
    db.add(doc)
    db.flush()
    db.add(KbIngestJob(kb_document_id=doc.id, stage="PENDING"))
    db.commit()
    db.refresh(doc)

    background.add_task(_run_ingest, doc.id, llm, rag)
    return _doc_out(doc)


async def _run_ingest(doc_id: uuid.UUID, llm: LLMClient, rag: RAG) -> None:
    from rag.ingest import ingest_document

    await ingest_document(doc_id, llm, rag)


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(KbDocument).order_by(KbDocument.created_at.desc()).all()
    return [_doc_out(d) for d in docs]


@router.get("/documents/{document_id}")
def get_document(document_id: uuid.UUID, db: Session = Depends(get_db)):
    doc = db.get(KbDocument, document_id)
    if doc is None:
        raise AppError(NOT_FOUND, "文档不存在")
    job = doc.jobs[-1] if doc.jobs else None
    return _doc_out(doc, job)


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    rag: RAG = Depends(get_rag),
):
    doc = db.get(KbDocument, document_id)
    if doc is None:
        raise AppError(NOT_FOUND, "文档不存在")
    try:
        rag.milvus.delete_document(str(doc.id))
        rag.neo4j.delete_document(str(doc.id))
        rag.minio.remove(rag.bucket_docs, doc.object_key)
    except Exception:  # noqa: BLE001
        pass
    db.delete(doc)
    db.commit()
