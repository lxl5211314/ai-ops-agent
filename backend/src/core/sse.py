import asyncio
import json
from collections.abc import AsyncIterator


def sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def heartbeat(interval: float = 15.0) -> AsyncIterator[str]:
    while True:
        await asyncio.sleep(interval)
        yield ": heartbeat\n\n"


async def merge_stream(main: AsyncIterator[str], hb: AsyncIterator[str]) -> AsyncIterator[str]:
    queue: asyncio.Queue = asyncio.Queue()
    stop = object()

    async def pump(source: AsyncIterator[str], tag):
        try:
            async for item in source:
                await queue.put((tag, item))
        except Exception as exc:  # noqa: BLE001
            await queue.put(("main", sse_event("error", {"code": "INTERNAL", "message": str(exc)})))
        finally:
            await queue.put((tag, stop))

    tasks = [asyncio.create_task(pump(main, "main")), asyncio.create_task(pump(hb, "hb"))]
    try:
        while True:
            tag, item = await queue.get()
            if item is stop:
                if tag == "main":
                    break
                continue
            yield item
    finally:
        for t in tasks:
            t.cancel()
