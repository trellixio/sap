"""
Contests.

Initialize testing with module wide fixtures.
"""

import asyncio
import typing
import hashlib

import pytest
import pytest_asyncio

from AppMain.asgi import document_models, initialize_beanie
from AppMain.settings import AppSettings
from tests.samples import DummyDoc, EmbeddedDummyDoc
from sap.tests.utils import generate_random_string


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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def populate_dummy_doc() -> typing.AsyncGenerator[bool, None]:
    """Populate doc in the dummy collection for testing."""
    description = generate_random_string(1024)
    for index in range(-10, 10):
        await DummyDoc(
            num=index,
            is_positive=index >= 0,
            hash=hashlib.md5(str(index).encode()).digest(),
            name=f"Document N{index}",
            description=description,
            listing=[index * 3, index * 5, index * 7, index * 9],
            data={f"attr{index}": description[index * 2 + 200 : index + 300]},
            info=EmbeddedDummyDoc(num=index * 5, name=f"EmbeddedDocument N{index}", limit=index * 17 + 20),
        ).create()

    count = await DummyDoc.find_all().count()
    print(f"Added {count} DummyDoc")

    yield True  # suspended until tests are done

    result = await DummyDoc.find_all().delete_many()
    assert result
    print(f"\nDeleted {result.deleted_count} DummyDoc")


# from celery.contrib.pytest import celery_app
