import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from infra.settings import ORCHESTRATION_MAX_PARALLEL_JOBS

_executor = ThreadPoolExecutor(max_workers=ORCHESTRATION_MAX_PARALLEL_JOBS)


async def run_sync(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, lambda: func(*args, **kwargs))
