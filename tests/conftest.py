import asyncio
import typing

import pytest

from AppMain.settings import AppSettings


@pytest.fixture(scope="session")
def event_loop() -> typing.Generator[asyncio.events.AbstractEventLoop, None, None]:
    """Force pytest fixtures to use async loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def celery_config() -> dict[str, str]:
    """Setting up Celery worker."""
    return {"broker_url": AppSettings.RABBITMQ.get_dns(), "result_backend": AppSettings.REDIS.get_dns()}


@pytest.fixture(scope="session")
def celery_enable_logging():
    """Enable logging for celery."""
    return True


# from celery.contrib.pytest import celery_app
