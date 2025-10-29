"""Tests for the cache_view decorator."""

import asyncio
from typing import Dict, Union

import pytest
from async_asgi_testclient import TestClient
from requests.models import Response

from fastapi import Request

from AppMain.asgi import app
from sap.fastapi.cache import cache_view


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.mark.asyncio
async def test_cache_view_basic(client: TestClient) -> None:
    """Test basic functionality of the cache_view decorator."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/basic/")
    @cache_view()
    async def test_endpoint_view_basic(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/basic/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/basic/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_query_params(client: TestClient) -> None:
    """Test cache_view with query parameters."""
    counter: Dict[str, int] = {"calls": 0}
    response: Response

    @app.get("/view/query/")
    @cache_view()
    async def test_endpoint_query(request: Request) -> Dict[str, Union[Dict[str, str], int]]:
        counter["calls"] += 1
        return {"query": dict(request.query_params), "counter": counter["calls"]}

    response = await client.get("/view/query/?param1=value1&param2=value2")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value1", "param2": "value2"}, "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/query/?param1=value1&param2=value2")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value1", "param2": "value2"}, "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/query/?param1=value3&param2=value4")
    assert response.status_code == 200
    assert response.json() == {"query": {"param1": "value3", "param2": "value4"}, "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_without_query_params(client: TestClient) -> None:
    """Test cache_view without including query parameters in the cache key."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/no-query/")
    @cache_view(include_query_params=False)
    async def test_endpoint_no_query(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/no-query/?param1=value1")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/no-query/?param1=value2")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_path_params(client: TestClient) -> None:
    """Test cache_view with path parameters."""
    counter: Dict[str, int] = {"calls": 0}
    response: Response

    @app.get("/view/path/{id_key}/")
    @cache_view()
    async def test_endpoint_path(request: Request, id_key: str) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"id_key": id_key, "counter": counter["calls"]}

    response = await client.get("/view/path/123/")
    assert response.status_code == 200
    assert response.json() == {"id_key": "123", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/path/123/")
    assert response.status_code == 200
    assert response.json() == {"id_key": "123", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/path/456/")
    assert response.status_code == 200
    assert response.json() == {"id_key": "456", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_without_path_params(client: TestClient) -> None:
    """Test cache_view without including path parameters in the cache key."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/no-path/{id_key}/")
    @cache_view(include_path_params=False)
    async def test_endpoint_no_path(request: Request, id_key: str) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"id_key": id_key, "counter": counter["calls"]}

    response = await client.get("/view/no-path/123/")
    assert response.status_code == 200
    assert response.json() == {"id_key": "123", "counter": 1}
    assert counter["calls"] == 1

    # Even though path params are not included in cache key, the path is different
    # so it's a different cache entry
    response = await client.get("/view/no-path/456/")
    assert response.status_code == 200
    assert response.json() == {"id_key": "456", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_custom_timeout(client: TestClient) -> None:
    """Test cache_view with a custom timeout."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/timeout/")
    @cache_view(cache_timeout=1)
    async def test_endpoint_timeout(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/timeout/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    await asyncio.sleep(1)

    response = await client.get("/view/timeout/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_custom_prefix(client: TestClient) -> None:
    """Test cache_view with a custom key prefix."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/prefix/")
    @cache_view(key_prefix="custom:prefix")
    async def test_endpoint_prefix(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/prefix/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/prefix/")
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_headers(client: TestClient) -> None:
    """Test cache_view with headers included in the cache key."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/headers/")
    @cache_view(include_headers=True)
    async def test_endpoint_headers(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/headers/", headers={"X-Test-Header": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/headers/", headers={"X-Test-Header": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/headers/", headers={"X-Test-Header": "value2"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_cookies(client: TestClient) -> None:
    """Test cache_view with cookies included in the cache key."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/cookies/")
    @cache_view(include_cookies=True)
    async def test_endpoint_cookies(request: Request) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": "test", "counter": counter["calls"]}

    response = await client.get("/view/cookies/", cookies={"test_cookie": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/cookies/", cookies={"test_cookie": "value1"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/cookies/", cookies={"test_cookie": "value2"})
    assert response.status_code == 200
    assert response.json() == {"data": "test", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_with_body(client: TestClient) -> None:
    """Test cache_view with request body included in the cache key."""
    counter: Dict[str, int] = {"calls": 0}

    @app.post("/view/body/")
    @cache_view(include_body=True)
    async def test_endpoint_body(request: Request) -> str:
        counter["calls"] += 1
        return f"counter: {counter['calls']}"

    response = await client.post("/view/body/", data=b"test_body_1")
    assert response.status_code == 200
    assert "counter: 1" in response.text
    assert counter["calls"] == 1

    response = await client.post("/view/body/", data=b"test_body_1")
    assert response.status_code == 200
    assert "counter: 1" in response.text
    assert counter["calls"] == 1

    response = await client.post("/view/body/", data=b"test_body_2")
    assert response.status_code == 200
    assert "counter: 2" in response.text
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_no_request_object() -> None:
    """Test cache_view when no Request object is found."""
    counter: Dict[str, int] = {"calls": 0}

    @cache_view()
    async def test_func_no_request(data: str) -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"data": data, "counter": counter["calls"]}

    result = await test_func_no_request("test1")
    assert result == {"data": "test1", "counter": 1}
    assert counter["calls"] == 1

    result = await test_func_no_request("test1")
    assert result == {"data": "test1", "counter": 2}
    assert counter["calls"] == 2


@pytest.mark.asyncio
async def test_cache_view_request_in_kwargs(client: TestClient) -> None:
    """Test cache_view when Request is passed as a keyword argument."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/kwargs/")
    @cache_view()
    async def test_endpoint_kwargs(*, request: Request, param: str = "default") -> Dict[str, Union[str, int]]:
        counter["calls"] += 1
        return {"param": param, "counter": counter["calls"]}

    response = await client.get("/view/kwargs/?param=test")
    assert response.status_code == 200
    assert response.json() == {"param": "test", "counter": 1}
    assert counter["calls"] == 1

    response = await client.get("/view/kwargs/?param=test")
    assert response.status_code == 200
    assert response.json() == {"param": "test", "counter": 1}
    assert counter["calls"] == 1


@pytest.mark.asyncio
async def test_cache_view_with_error(client: TestClient) -> None:
    """Test cache_view when the view function raises an error."""
    counter: Dict[str, int] = {"calls": 0}

    @app.get("/view/error/")
    @cache_view()
    async def test_endpoint_error(request: Request) -> None:
        counter["calls"] += 1
        raise ValueError("Test error")

    with pytest.raises(ValueError):
        await client.get("/view/error/")

    assert counter["calls"] == 1

    with pytest.raises(ValueError):
        await client.get("/view/error/")

    assert counter["calls"] == 2
