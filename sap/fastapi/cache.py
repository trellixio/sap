# pylint: disable=too-complex, too-many-branches
"""Cache utilities for FastAPI views."""

import functools
import json
import typing
from datetime import timedelta

from redis.asyncio.client import Redis

from fastapi import Request

from .serializers import CustomJSONEncoder


class CacheParam:
    """Handle connection to Redis cache."""

    redis_url: typing.ClassVar[str] = ""
    cache_timeout: typing.ClassVar[int] = 60 * 60 * 1  #  1 hour


def cache_view(
    *,
    cache_timeout: int = 60 * 60 * 1,  #  1 hour
    key_prefix: str | None = None,
    include_query_params: bool = True,
    include_path_params: bool = True,
    include_headers: bool = False,
    include_cookies: bool = False,
    include_body: bool = False,
) -> typing.Callable[[typing.Callable[..., typing.Any]], typing.Callable[..., typing.Any]]:
    """
    Cache FastAPI view function results.

    Args:
        cache_timeout: Timeout in seconds for the cache entry. If None, uses the default to 1 hour.
        key_prefix: Prefix for the cache key. If None, uses the function name.
        include_query_params: Whether to include query parameters in the cache key.
        include_path_params: Whether to include path parameters in the cache key.
        include_headers: Whether to include headers in the cache key.
        include_cookies: Whether to include cookies in the cache key.
        include_body: Whether to include request body in the cache key.

    Returns:
        A decorator function that can be applied to FastAPI view functions.
    """

    def decorator(func: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
        """Define a decorator to cache FastAPI view function results."""

        @functools.wraps(func)
        async def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
            """Define a wrapper to cache FastAPI view function results."""
            # Extract the request object from args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request is None:
                for value in kwargs.values():
                    if isinstance(value, Request):
                        request = value
                        break

            if request is None:
                # If no request object found, just call the function without caching
                return await func(*args, **kwargs)

            # Build the cache key
            key_parts = []

            # Add prefix
            if key_prefix:
                key_parts.append(key_prefix)
            else:
                key_parts.append(f"{func.__module__}.{func.__name__}")

            # Add path
            key_parts.append(request.url.path)

            # Add query parameters if requested
            if include_query_params and request.query_params:
                query_params = dict(request.query_params)
                # Sort to ensure consistent keys
                key_parts.append(json.dumps(query_params, sort_keys=True))

            # Add path parameters if requested
            if include_path_params and request.path_params:
                path_params = dict(request.path_params)
                # Sort to ensure consistent keys
                key_parts.append(json.dumps(path_params, sort_keys=True))

            # Add headers if requested
            if include_headers and request.headers:
                headers = dict(request.headers)
                # Sort to ensure consistent keys
                key_parts.append(json.dumps(headers, sort_keys=True))

            # Add cookies if requested
            if include_cookies and request.cookies:
                cookies = dict(request.cookies)
                # Sort to ensure consistent keys
                key_parts.append(json.dumps(cookies, sort_keys=True))

            # Add body if requested
            if include_body:
                try:  # pylint: disable=too-many-try-statements
                    body = await request.body()
                    if body:
                        key_parts.append(body.decode())
                except Exception:  # pylint: disable=broad-exception-caught
                    # If we can't read the body, just skip it
                    pass

            # Join all parts with a separator
            cache_key = ":".join(key_parts)

            # Try to get from cache
            async with Redis.from_url(url=CacheParam.redis_url) as redis_client:
                cached_data = await redis_client.get(cache_key)

                if cached_data:
                    # Cache hit, return the cached data
                    return json.loads(cached_data)

                # Cache miss, call the function
                result = await func(*args, **kwargs)

                # Cache the result
                await redis_client.set(
                    cache_key,
                    json.dumps(result, cls=CustomJSONEncoder),
                    timedelta(seconds=cache_timeout),
                )

                return result

        return wrapper

    return decorator
