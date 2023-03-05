"""
# Middleware.

This module contains generic middleware to perform repetitive actions on each request.
Learn more: https://fastapi.tiangolo.com/tutorial/middleware/
"""

import traceback
import typing

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from sap.loggers import logger


class LogServerErrorMiddleware(BaseHTTPMiddleware):
    """Return the server error response in a JSON object for debugging.

    Make sure that this middleware is not enable in production
    as it could leak important security information.

    There is a bug using BaseHTTPMiddleware, Jinja2, and starlette.TestClient
    https://github.com/encode/starlette/issues/472

    Using async_asgi_testclient.TestClient fix the issue while waiting for an official starlette fix
    https://github.com/tiangolo/fastapi/issues/806
    """

    async def dispatch(
        self, request: Request, call_next: typing.Callable[[Request], typing.Awaitable[Response]]
    ) -> Response:
        """Render server error."""
        try:
            return await call_next(request)
        except Exception as exc:  # pylint: disable=broad-except; pragma: no cover
            logger.exception(exc)
            trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
            return JSONResponse(content={"traceback": trace}, status_code=500)
