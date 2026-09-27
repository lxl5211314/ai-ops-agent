import asyncio
import mimetypes
import uuid

from llm.client import LLMClient
from models.kb import STATUS_FAILED, STATUS_INDEXED, KbDocument, KbIngestJob
from rag.chunking import chunk_text
from rag.clients import RAG

GRAPH_PROMPT = """你是信息抽取器。从下面文档片段中抽取实体和关系，只输出 JSON：
{"entities": [{"name": "...", "type": "服务|组件|故障现象|原因|方案|其他"}],
 "relations": [{"subject": "...", "relation": "...", "object": "..."}]}
片段：
{chunk}"""


def _decode(raw: bytes) -> str:
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def guess_content_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def new_object_key(filename: str) -> str:
    return f"{uuid.uuid4().hex}/{filename}"


async def ingest_document(doc_id: uuid.UUID, llm: LLMClient, rag: RAG) -> None:
    from core.db import SessionLocal

    def stage(stage_name: str, detail: str | None = None, failed: bool = False):
        db = SessionLocal()
        try:
            doc = db.get(KbDocument, doc_id)
            if doc is None:
                return
            if failed:
                doc.status = STATUS_FAILED
                doc.error_message = (detail or "")[:500]
            db.add(KbIngestJob(kb_document_id=doc_id, stage=stage_name, detail=detail))
            db.commit()
        finally:
            db.close()

    try:
        db = SessionLocal()
        try:
            doc = db.get(KbDocument, doc_id)
            if doc is None:
                return
            object_key = doc.object_key
            title = doc.title
            category = doc.category
        finally:
            db.close()

        stage("PARSING")
        raw = rag.minio.get(rag.bucket_docs, object_key)
        text = _decode(raw)

        stage("CHUNKING")
        chunks = chunk_text(text)
        if not chunks:
            raise ValueError("文档内容为空或无法解析出文本")

        stage("EMBEDDING")
        vectors = await llm.embed([c for _, c in chunks])
        rag.milvus.insert(
            [
                {
                    "chunk_text": chunk,
                    "document_id": str(doc_id),
                    "heading": heading or title,
                    "category": category,
                }
                for (heading, chunk), _ in zip(chunks, vectors, strict=False)
            ],
            vectors,
        )

        stage("GRAPH_BUILD")
        entities: dict[str, dict] = {}
        relations: list[dict] = []
        for _, chunk in chunks[:20]:
            try:
                data = await llm.chat_json(
                    [{"role": "user", "content": GRAPH_PROMPT.format(chunk=chunk[:2000])}]
                )
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                continue
            for ent in data.get("entities", []) or []:
                if ent.get("name"):
                    entities[ent["name"]] = ent
            relations.extend(data.get("relations", []) or [])
        if entities:
            rag.neo4j.write_graph(str(doc_id), list(entities.values()), relations)

        db = SessionLocal()
        try:
            doc = db.get(KbDocument, doc_id)
            doc.chunk_count = len(chunks)
            doc.graph_node_count = len(entities)
            doc.status = STATUS_INDEXED
            doc.error_message = None
            db.add(KbIngestJob(kb_document_id=doc_id, stage="DONE"))
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        stage("FAILED", str(exc)[:500], failed=True)


async def start_ingest(doc_id: uuid.UUID, llm: LLMClient, rag: RAG) -> None:
    asyncio.create_task(ingest_document(doc_id, llm, rag))
