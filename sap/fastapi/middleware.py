"""
# Middleware.

This module contains generic middleware to perform repetitive actions on each request.
Learn more: https://fastapi.tiangolo.com/tutorial/middleware/
"""

from __future__ import annotations

import traceback
from typing import Awaitable, Callable, List, Type

import beanie
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from sap.beanie.client import BeanieClient
from sap.loggers import logger
from sap.settings import DatabaseParams


class LogServerErrorMiddleware(BaseHTTPMiddleware):
    """Return the server error response in a JSON object for debugging.

    Make sure that this middleware is not enable in production
    as it could leak important security information.

    There is a bug using BaseHTTPMiddleware, Jinja2, and starlette.TestClient
    https://github.com/encode/starlette/issues/472

    Using async_asgi_testclient.TestClient fix the issue while waiting for an official starlette fix
    https://github.com/tiangolo/fastapi/issues/806
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Render server error."""
        try:
            return await call_next(request)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(exc)
            trace = traceback.format_exception(type(exc), exc, exc.__traceback__)
            return JSONResponse(content={"traceback": trace}, status_code=500)


class InitBeanieMiddleware:
    """Middleware to initialize a connection to Mongo database."""

    app: ASGIApp
    mongo_params: DatabaseParams
    document_models: List[Type[beanie.Document]] | List[Type[beanie.View]] | List[str]
    force: bool = False

    def __init__(
        self,
        app: ASGIApp,
        mongo_params: DatabaseParams,
        document_models: List[Type[beanie.Document]] | List[Type[beanie.View]] | List[str],
        force: bool = False,
    ) -> None:
        """Initialize Middleware."""
        self.app = app
        self.mongo_params = mongo_params
        self.document_models = document_models
        self.force = force

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run Middleware."""
        await BeanieClient.init(
            mongo_params=self.mongo_params,
            document_models=self.document_models,
            force=self.force,
        )
        await self.app(scope, receive, send)
