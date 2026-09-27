import json
import re
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from core.config import Settings


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key or "empty",
            timeout=120,
        )
        self._embed_client = AsyncOpenAI(
            base_url=settings.embedding_base_url or settings.llm_base_url or None,
            api_key=settings.embedding_api_key or settings.llm_api_key or "empty",
            timeout=60,
        )

    async def stream_chat(
        self, messages: list[dict], temperature: float = 0.2
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def chat_json(self, messages: list[dict], temperature: float = 0.1) -> dict:
        resp = await self._client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=temperature,
        )
        content = resp.choices[0].message.content or ""
        return _extract_json(content)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        resp = await self._embed_client.embeddings.create(
            model=self.settings.embedding_model, input=texts
        )
        return [item.embedding for item in resp.data]

    async def ping(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:  # noqa: BLE001
            return False
