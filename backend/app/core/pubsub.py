import asyncio
from collections import defaultdict
from typing import Dict, Set

_run_queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
_global_queues: Set[asyncio.Queue] = set()


async def subscribe_run(run_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _run_queues[run_id].add(q)
    return q


async def unsubscribe_run(run_id: str, q: asyncio.Queue) -> None:
    _run_queues[run_id].discard(q)
    if not _run_queues[run_id]:
        _run_queues.pop(run_id, None)


async def subscribe_global() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _global_queues.add(q)
    return q


async def unsubscribe_global(q: asyncio.Queue) -> None:
    _global_queues.discard(q)


async def publish_run(run_id: str, data: dict) -> None:
    for q in list(_run_queues.get(run_id, set())):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass
    for q in list(_global_queues):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            pass
