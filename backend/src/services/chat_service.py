from collections.abc import AsyncIterator

from llm.client import LLMClient
from rag.retrieval import retrieve

SYSTEM_PROMPT = """你是运维助手「小龙」，服务企业内部用户。回答运维相关问题时：
1. 先给出「原因分析」：列出最可能的原因（按可能性排序）
2. 再给出「解决方案」：给出可操作的步骤，标注命令/配置示例
3. 若提供了参考资料，优先结合参考资料并注明引用来源
4. 无法确定时明确说明不确定并请求补充信息，禁止编造
使用中文，使用 Markdown 结构化输出。"""


def _format_context(items: list[dict]) -> str:
    if not items:
        return ""
    lines = ["参考资料："]
    for i, it in enumerate(items, 1):
        lines.append(f"[{i}] ({it.get('heading', '')}) {it.get('chunk_text', '')[:600]}")
    return "\n".join(lines)


def _history(messages: list[dict], limit: int = 12) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in messages[-limit:]]


async def stream_reply(
    llm: LLMClient,
    user_text: str,
    history: list[dict],
    rag_store=None,
) -> AsyncIterator[dict]:
    """Yield events: {"event": "sources"|"delta", ...}."""
    sources: list[dict] = []
    if rag_store is not None:
        try:
            hits = await retrieve(rag_store, llm, user_text)
            for hit in hits[:6]:
                sources.append(
                    {
                        "title": hit.get("heading") or "企业知识图谱",
                        "category": hit.get("category", ""),
                        "snippet": hit.get("chunk_text", "")[:200],
                    }
                )
        except Exception:  # noqa: BLE001
            hits = []
    else:
        hits = []

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    context = _format_context(hits)
    messages.extend(_history(history))
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": user_text})

    if sources:
        yield {"event": "sources", "data": {"items": sources}}

    try:
        async for delta in llm.stream_chat(messages):
            yield {"event": "delta", "data": {"text": delta}}
    except Exception as exc:  # noqa: BLE001
        yield {
            "event": "error",
            "data": {"code": "LLM_UNAVAILABLE", "message": f"模型服务不可用：{exc}"},
        }
        return
    yield {"event": "done", "data": {"finish_reason": "stop"}}


async def collect_reply(
    llm: LLMClient, user_text: str, history: list[dict], rag_store=None
) -> tuple[str, list[dict]]:
    text_parts: list[str] = []
    sources: list[dict] = []
    async for ev in stream_reply(llm, user_text, history, rag_store=rag_store):
        if ev["event"] == "delta":
            text_parts.append(ev["data"]["text"])
        elif ev["event"] == "sources":
            sources = ev["data"]["items"]
        elif ev["event"] == "error":
            raise RuntimeError(ev["data"]["message"])
    return "".join(text_parts), sources
