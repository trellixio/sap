"""
Contests.

Initialize testing with module wide fixtures.
"""
import asyncio
import typing

import pytest
import pytest_asyncio

from AppMain.asgi import document_models, initialize_beanie
from AppMain.settings import AppSettings
from tests.worker.samples import DummyDoc


@pytest.fixture(scope="session")
def event_loop() -> typing.Generator[asyncio.events.AbstractEventLoop, None, None]:
    """Force pytest fixtures to use async loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialise_db() -> typing.AsyncGenerator[bool, None]:
    """Initialize DB connection for all tests."""
    print("Connecting to MongoDB")
    print("Initializing Beanie")

    document_models.append(DummyDoc)

    await initialize_beanie()

    yield True  # suspended until tests are done

    print("Disconnecting from MongoDB")


@pytest.fixture(scope="session")
def celery_config() -> dict[str, str]:
    """Set up Celery worker."""
    return {"broker_url": AppSettings.RABBITMQ.get_dns(), "result_backend": AppSettings.REDIS.get_dns()}


@pytest.fixture(scope="session")
def celery_enable_logging() -> bool:
    """Enable logging for celery."""
    return True


# from celery.contrib.pytest import celery_app
