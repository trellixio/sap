"""
Test Middleware.

Test request middleware helpers.
"""

import json
from typing import cast

import pytest

from fastapi import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp

from sap.fastapi.middleware import LogServerErrorMiddleware


async def unused_app(*args: object, **kwargs: object) -> None:
    """Satisfy the middleware constructor without handling a request."""


def http_request() -> Request:
    """Build a minimal HTTP request."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/middleware/",
        "raw_path": b"/middleware/",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8000),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_log_server_error_middleware_success() -> None:
    """Pass the downstream response through when the view succeeds."""

    async def call_next(request: Request) -> PlainTextResponse:
        """Return a successful response."""
        return PlainTextResponse("ok")

    middleware = LogServerErrorMiddleware(app=cast(ASGIApp, unused_app))
    response = await middleware.dispatch(http_request(), call_next)

    assert response.status_code == 200
    assert response.body == b"ok"


@pytest.mark.asyncio
async def test_log_server_error_middleware_exception() -> None:
    """Return a JSON traceback when the view raises."""

    async def call_next(request: Request) -> PlainTextResponse:
        """Raise an unexpected error."""
        raise RuntimeError("boom")

    middleware = LogServerErrorMiddleware(app=cast(ASGIApp, unused_app))
    response = await middleware.dispatch(http_request(), call_next)

    assert isinstance(response, JSONResponse)
    assert response.status_code == 500
    assert "traceback" in json.loads(bytes(response.body))
