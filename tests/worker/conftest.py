"""
Fixtures.

Fixtures provides test scenario with baseline data needed to operate.
Learn more: https://docs.pytest.org/en/6.2.x/fixture.html
"""

import typing

import pytest_asyncio

from .samples import DummyDoc


@pytest_asyncio.fixture(scope="package", autouse=True)
async def populate_dummy_doc() -> typing.AsyncGenerator[bool, None]:
    """Populate doc in the dummy collection for testing."""
    for index in range(-10, 10):
        await DummyDoc(num=index).create()

    count = await DummyDoc.find_all().count()
    print(f"Added {count} DummyDoc")

    yield True  # suspended until tests are done

    result = await DummyDoc.find_all().delete_many()
    assert result
    print(f"\nDeleted {result.deleted_count} DummyDoc")
