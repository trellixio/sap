"""
Test Beans Client.

Test Beans API client wrapper and common errors.
"""

from unittest import mock

import httpx
import pytest

from AppMain.settings import AppSettings
from sap.rest import BeansClient, RestClient, RestData, rest_exceptions

integration_params = AppSettings.TOKENIFY
testcases_params = AppSettings.TESTCASES


@pytest.mark.asyncio
async def test_beans_api_get_access_token_invalid() -> None:
    """Test retrieving access_token on oauth."""
    with pytest.raises(rest_exceptions.Rest404Error):
        await BeansClient.get_access_token(
            "invalid_oauth_code",
            beans_public=integration_params.beans_public,
            beans_secret=integration_params.beans_secret,
        )


@pytest.mark.asyncio
async def test_beans_api_get() -> None:
    """Test retrieving a RuleType object on Beans API."""
    data = await BeansClient(access_token="").get("liana/rule_type/rule:liana:currency_spent")
    assert isinstance(data.response, httpx.Response)
    assert data["object"] == "rule_type"


@pytest.mark.asyncio
async def test_beans_api_post() -> None:
    """Test creating object without authentication."""
    with pytest.raises(rest_exceptions.Rest401Error):
        await BeansClient(access_token="").post("liana/rule/", json={"type": "rule:liana:currency_spent"})

    with pytest.raises(rest_exceptions.Rest400Error):
        await BeansClient(access_token=testcases_params.beans_access_token).post(
            "liana/credit/", json={"rule": "rule:liana:currency_spent"}
        )


@pytest.mark.asyncio
async def test_beans_api_put() -> None:
    """Test updating object without permission."""
    with pytest.raises(rest_exceptions.Rest403Error):
        await BeansClient(access_token=testcases_params.beans_card_id).put(
            "liana/rule/rule:liana:currency_spent", json={}
        )


@pytest.mark.asyncio
async def test_beans_api_delete() -> None:
    """Test method not allowed."""
    with pytest.raises(rest_exceptions.Rest405Error):
        await BeansClient(access_token="").delete("liana/rule_type/rule:liana:currency_spent")


@pytest.mark.asyncio
async def test_rest_client_patch_list_and_basic_auth() -> None:
    """Patch through basic auth and wrap a JSON list response."""
    client = RestClient("user", "secret")
    async with client._get_client() as http:  # pylint: disable=protected-access
        assert isinstance(http.auth, httpx.BasicAuth)

    request = httpx.Request("PATCH", "https://example.com/items")
    response = httpx.Response(200, json=[{"id": 1}], request=request)

    async def fake_request(*args: object, **kwargs: object) -> httpx.Response:
        """Return a canned list response."""
        assert args[1] == "PATCH"
        return response

    with mock.patch.object(httpx.AsyncClient, "request", fake_request):
        data = await client.patch("https://example.com/items", json={"a": 1})

    assert data["data"] == [{"id": 1}]
    assert data.response is response


@pytest.mark.asyncio
async def test_beans_get_access_token_unwraps_card() -> None:
    """Unwrap a card object into its id when exchanging an oauth code."""

    async def fake_get(*args: object, **kwargs: object) -> RestData:
        """Return an integration key whose card is still an object."""
        assert str(args[1]).endswith("core/auth/integration_key/code")
        return RestData({"card": {"id": "card_1"}})

    with mock.patch.object(RestClient, "get", fake_get):
        data = await BeansClient.get_access_token("code", "pub", "secret")

    assert data["card"] == "card_1"


@pytest.mark.asyncio
async def test_beans_api_invalid_path() -> None:
    """Test query a bad path."""
    with pytest.raises(rest_exceptions.Rest405Error):
        await BeansClient(access_token="").get("liana/rule_type_bad")
