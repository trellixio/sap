"""Tests for the cache_view decorator."""

import time
from datetime import datetime
from typing import Any, Dict, Union

import pytest
from async_asgi_testclient import TestClient
from requests.models import Response

from fastapi import Request

from AppMain.asgi import app
from sap.fastapi.cache import cache_view


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_cache_view_basic(client: TestClient) -> None:
    """Test basic functionality of the cache_view decorator."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/basic/")
    @cache_view()
    async def test_endpoint_view_basic(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call - should hit the database
    response = await client.get("/view/basic/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    # Counter should have increased
    assert counter["calls"] == 1

    # Second call - should use the cache
    response = await client.get("/view/basic/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    # Counter should not have increased
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_query_params(client: TestClient) -> None:
    """Test cache_view with query parameters."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}
    response: Response

    @app.get("/view/query/")
    @cache_view()
    async def test_endpoint_query(request: Request) -> Dict[str, Union[Dict[str, str], int]]:
        counter["calls"] += 1
        return {"query": dict(request.query_params), "counter": counter["calls"]}

    # First call with query params
    response = await client.get("/view/query/?param1=value1&param2=value2")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value1", "param2": "value2"}, "counter": 1}
    assert counter["calls"] == 1

    # Second call with the same query params
    response = await client.get("/view/query/?param1=value1&param2=value2")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value1", "param2": "value2"}, "counter": 1}
    assert counter["calls"] == 1

    # Call with different query params
    response = await client.get("/view/query/?param1=value3&param2=value4")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value3", "param2": "value4"}, "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_without_query_params(client: TestClient) -> None:
    """Test cache_view without including query parameters in the cache key."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/no-query/")
    @cache_view(include_query_params=False)
    async def test_endpoint_no_query(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call with query params
    response = await client.get("/view/no-query/?param1=value1")
    assert response.status_code == 200
    print(response.json())
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Second call with different query params
    response = await client.get("/view/no-query/?param1=value2")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_path_params(client: TestClient) -> None:
    """Test cache_view with path parameters."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}
    response: Response

    @app.get("/view/path/{id}/")
    @cache_view()
    async def test_endpoint_path(request: Request, id: str) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"id": id, "counter": counter["calls"]}

    # First call with path param
    response = await client.get("/view/path/123/")
    assert response.status_code == 200
    assert response.json() == {"id": "123", "counter": 1}
    assert counter["calls"] == 1

    # Second call with the same path param
    response = await client.get("/view/path/123/")
    assert response.status_code == 200
    assert response.json() == {"id": "123", "counter": 1}
    assert counter["calls"] == 1

    # Call with a different path param
    response = await client.get("/view/path/456/")
    assert response.status_code == 200
    assert response.json() == {"id": "456", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_custom_timeout(client: TestClient) -> None:
    """Test cache_view with a custom timeout."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/timeout/")
    @cache_view(cache_timeout=1)  # 1 seconds
    async def test_endpoint_timeout(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call
    response = await client.get("/view/timeout/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    time.sleep(1)

    # Second call - should use the cache
    response = await client.get("/view/timeout/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_custom_prefix(client: TestClient) -> None:
    """Test cache_view with a custom key prefix."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/prefix/")
    @cache_view(key_prefix="custom:prefix")
    async def test_endpoint_prefix(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call
    response = await client.get("/view/prefix/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Second call - should use the cache
    response = await client.get("/view/prefix/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_headers(client: TestClient) -> None:
    """Test cache_view with headers included in the cache key."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/headers/")
    @cache_view(include_headers=True)
    async def test_endpoint_headers(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call with a header
    response = await client.get("/view/headers/", headers={"X-Test-Header": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Second call with the same header
    response = await client.get("/view/headers/", headers={"X-Test-Header": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Call with a different header
    response = await client.get("/view/headers/", headers={"X-Test-Header": "value2"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_cookies(client: TestClient) -> None:
    """Test cache_view with cookies included in the cache key."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/cookies/")
    @cache_view(include_cookies=True)
    async def test_endpoint_cookies(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    # First call with a cookie
    response = await client.get("/view/cookies/", cookies={"test_cookie": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Second call with the same cookie
    response = await client.get("/view/cookies/", cookies={"test_cookie": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    # Call with a different cookie
    response = await client.get("/view/cookies/", cookies={"test_cookie": "value2"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_error(client: TestClient) -> None:
    """Test cache_view when the view function raises an error."""
    # Create a counter to track function calls
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/error/")
    @cache_view()
    async def test_endpoint_error(request: Request) -> None:
        counter["calls"] += 1
        raise ValueError("Test error")

    # Call the endpoint
    with pytest.raises(ValueError):
        await client.get("/view/error/")

    # Counter should have increased
    assert counter["calls"] == 1

    # Call the endpoint
    with pytest.raises(ValueError):
        await client.get("/view/error/")

    # Counter should have increased
    assert counter["calls"] == 2
