"""
# FastAPI.

This module contains the helpers to use Beanie in FastAPI apps.
Learn more: https://fastapi.tiangolo.com/tutorial/middleware/
"""

from __future__ import annotations

from typing import ClassVar, List, Type

import beanie
from starlette.types import ASGIApp, Receive, Scope, Send

from sap.settings import DatabaseParams

from .client import BeanieClient


class InitBeanieMiddleware:
    """Middleware to initialize a connection to Mongo database."""

    app: ASGIApp
    mongo_params: DatabaseParams
    document_models: List[Type[beanie.Document]] | List[Type[beanie.View]] | List[str]
    force: bool = False
    beanie_client_class: ClassVar[Type[BeanieClient]] = BeanieClient

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
        await self.beanie_client_class.init(
            mongo_params=self.mongo_params,
            document_models=self.document_models,
            force=self.force,
        )
        await self.app(scope, receive, send)
