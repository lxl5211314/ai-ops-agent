from functools import lru_cache

from llm.client import LLMClient


@lru_cache
def get_llm() -> LLMClient:
    from core.config import get_settings

    return LLMClient(get_settings())
