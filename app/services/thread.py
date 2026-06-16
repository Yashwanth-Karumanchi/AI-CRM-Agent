import asyncio
from functools import wraps, partial
from typing import Callable, Any
from app.logger import get_logger

logger = get_logger(__name__)

# Shared thread pool — all gspread calls go here
_executor = None


def get_executor():
    global _executor
    if _executor is None:
        from concurrent.futures import ThreadPoolExecutor
        _executor = ThreadPoolExecutor(
            max_workers=20,
            thread_name_prefix="sheets_worker"
        )
    return _executor


async def run_in_thread(func: Callable, *args, **kwargs) -> Any:
    """
    Run any blocking/synchronous function in a thread pool
    without blocking the async event loop.

    Usage:
        result = await run_in_thread(ws.get_all_records)
        result = await run_in_thread(ws.append_row, [1,2,3])
    """
    loop = asyncio.get_event_loop()
    if kwargs:
        fn = partial(func, **kwargs)
        return await loop.run_in_executor(
            get_executor(), fn, *args
        )
    return await loop.run_in_executor(
        get_executor(), func, *args
    )


def make_async(func: Callable) -> Callable:
    """
    Decorator: converts a sync function to async
    by running it in the thread pool.

    Usage:
        @make_async
        def my_sync_function(x, y):
            return x + y

        result = await my_sync_function(1, 2)
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await run_in_thread(func, *args, **kwargs)
    return wrapper