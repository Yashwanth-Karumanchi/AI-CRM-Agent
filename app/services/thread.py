import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps, partial
from typing import Callable, Any
from app.logger import get_logger

logger = get_logger(__name__)

# ── Shared thread pool ─────────────────────────────────
# All blocking I/O (gspread, Gmail, Calendar) goes here.
# 20 workers = 20 concurrent blocking calls maximum.
_executor: ThreadPoolExecutor | None = None
_EXECUTOR_MAX_WORKERS = 20


def get_executor() -> ThreadPoolExecutor:
    """Return shared thread pool, creating it if needed"""
    global _executor
    if _executor is None or _executor._shutdown:
        _executor = ThreadPoolExecutor(
            max_workers=_EXECUTOR_MAX_WORKERS,
            thread_name_prefix="aria_worker"
        )
        logger.info(
            f"Thread pool created: "
            f"{_EXECUTOR_MAX_WORKERS} workers"
        )
    return _executor


async def run_in_thread(
    func: Callable,
    *args,
    **kwargs
) -> Any:
    """
    Run any blocking/synchronous function in the
    shared thread pool without blocking the event loop.

    Usage:
        # Simple call
        records = await run_in_thread(ws.get_all_records)

        # With positional args
        await run_in_thread(ws.append_row, [1, 2, 3])

        # With keyword args
        await run_in_thread(ws.update, "A1", value="foo")
    """
    loop = asyncio.get_event_loop()

    if kwargs:
        # Bind kwargs into the callable
        bound = partial(func, **kwargs)
        return await loop.run_in_executor(
            get_executor(), bound, *args
        )

    return await loop.run_in_executor(
        get_executor(), func, *args
    )


def make_async(func: Callable) -> Callable:
    """
    Decorator: wraps a synchronous function so it
    runs in the thread pool when awaited.

    Usage:
        @make_async
        def slow_sheets_call(x):
            return spreadsheet.get(x)

        result = await slow_sheets_call("A1:Z100")
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_thread(func, *args, **kwargs)
    return wrapper


def shutdown_executor():
    """
    Gracefully shut down thread pool.
    Call this on app shutdown.
    """
    global _executor
    if _executor and not _executor._shutdown:
        _executor.shutdown(wait=True)
        logger.info("Thread pool shut down")
        _executor = None