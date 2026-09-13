"""Background job queue abstraction.

LocalJobQueue uses FastAPI BackgroundTasks / asyncio.
This can be swapped for Celery, RQ, etc. by implementing AbstractJobQueue.
"""
from __future__ import annotations
import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Callable, Any

logger = logging.getLogger("codepilot.jobs")


class AbstractJobQueue(ABC):
    @abstractmethod
    async def enqueue(self, fn: Callable, *args, **kwargs) -> None:
        """Schedule fn(*args, **kwargs) for background execution."""
        ...


class LocalJobQueue(AbstractJobQueue):
    """Runs jobs in asyncio background tasks within the same process."""

    async def enqueue(self, fn: Callable, *args, **kwargs) -> None:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(None, lambda: _run_sync(fn, *args, **kwargs))


def _run_sync(fn: Callable, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.error(f"Background job failed: {fn.__name__}: {e}", exc_info=True)


# Singleton queue used by the app
_queue: LocalJobQueue = LocalJobQueue()


def get_job_queue() -> LocalJobQueue:
    return _queue
