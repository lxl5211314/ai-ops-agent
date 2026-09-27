from llm.client import LLMClient
from rag.chunking import extract_keywords
from rag.clients import RAG


async def retrieve(rag: RAG, llm: LLMClient, query: str, top_k: int = 5) -> list[dict]:
    """Hybrid retrieval: Milvus vector recall + Neo4j entity expansion.

    Degrades to an empty list when RAG infrastructure is unavailable.
    """
    results: list[dict] = []
    try:
        vectors = await llm.embed([query])
        results.extend(rag.milvus.search(vectors[0], top_k=top_k))
    except Exception:  # noqa: BLE001
        pass
    try:
        facts = rag.neo4j.expand(extract_keywords(query), limit=8)
        for fact in facts:
            results.append(
                {
                    "chunk_text": fact,
                    "document_id": "",
                    "heading": "企业知识图谱",
                    "category": "graph",
                    "score": 0.0,
                }
            )
    except Exception:  # noqa: BLE001
        pass
    return results[: top_k + 8]
