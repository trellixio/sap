"""
Test Beans Client.

Test Beans API client wrapper and common errors.
"""

import httpx
import pytest

from AppMain.settings import AppSettings
from sap.rest import BeansClient, rest_exceptions

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
async def test_beans_api_invalid_path() -> None:
    """Test query a bad path."""
    with pytest.raises(rest_exceptions.Rest405Error):
        await BeansClient(access_token="").get("liana/rule_type_bad")
