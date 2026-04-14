"""Shared utility decorators for the market simulator."""

import asyncio
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar, Any

F = TypeVar("F", bound=Callable[..., Any])


def rate_limited(max_per_second: float) -> Callable[[F], F]:
    """Decorator that throttles a *synchronous* function to at most
    ``max_per_second`` calls per second.

    Uses ``time.sleep()`` so it is **not** safe to apply to coroutines or any
    function called from within an ``asyncio`` event loop.  For async contexts
    use :func:`async_rate_limited` instead.

    Args:
        max_per_second: Maximum number of calls permitted per second.

    Returns:
        A decorator that wraps the target function with rate limiting.

    Example::

        @rate_limited(5)
        def fetch_price(symbol: str) -> dict: ...
    """
    min_interval: float = 1.0 / float(max_per_second)

    def decorate(func: F) -> F:
        last_time_called: list[float] = [0.0]

        @wraps(func)
        def rate_limited_function(*args: Any, **kwargs: Any) -> Any:
            elapsed = time.monotonic() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            last_time_called[0] = time.monotonic()
            return func(*args, **kwargs)

        return rate_limited_function  # type: ignore[return-value]

    return decorate


def async_rate_limited(max_per_second: float) -> Callable[[F], F]:
    """Decorator that throttles an *async* function to at most
    ``max_per_second`` calls per second.

    Uses ``await asyncio.sleep()`` so the event loop is **never blocked**,
    making this safe to use on coroutines running inside an ``asyncio`` event
    loop (e.g. WebSocket handlers).

    Args:
        max_per_second: Maximum number of calls permitted per second.

    Returns:
        A decorator that wraps the target coroutine with async rate limiting.

    Example::

        @async_rate_limited(2)
        async def stream_price(websocket) -> None: ...
    """
    min_interval: float = 1.0 / float(max_per_second)

    def decorate(func: F) -> F:
        last_time_called: list[float] = [0.0]

        @wraps(func)
        async def async_rate_limited_function(*args: Any, **kwargs: Any) -> Any:
            elapsed = asyncio.get_event_loop().time() - last_time_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                await asyncio.sleep(left_to_wait)
            last_time_called[0] = asyncio.get_event_loop().time()
            return await func(*args, **kwargs)

        return async_rate_limited_function  # type: ignore[return-value]

    return decorate
