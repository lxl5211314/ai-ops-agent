import asyncio

_QUEUES: dict[str, asyncio.Queue] = {}


def publish(analysis_id: str, event: str, data: dict) -> None:
    q = _QUEUES.get(analysis_id)
    if q is not None:
        q.put_nowait((event, data))


async def subscribe(analysis_id: str) -> asyncio.Queue:
    q = _QUEUES.setdefault(analysis_id, asyncio.Queue())
    return q


def unsubscribe(analysis_id: str) -> None:
    _QUEUES.pop(analysis_id, None)
