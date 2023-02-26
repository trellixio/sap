"""
Test Utils.

Test xlib.utils functions.
"""
import typing

import pytest
from async_asgi_testclient import TestClient

from fastapi import Request

from AppMain.asgi import app
from sap.fastapi import utils

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict


@pytest.mark.parametrize(
    ("data_input", "data_output"),
    [
        (
            [{"loc": ("a",), "msg": "message", "type": "value_error.str.regex"}],
            {"a": {"msg": "message", "type": "value_error.str.regex"}},
        ),
        (
            [{"loc": ("a", "b"), "msg": "message", "type": "value_error.str.regex", "ctx": {"k": "v"}}],
            {"a": {"b": {"msg": "message", "type": "value_error.str.regex", "ctx": {"k": "v"}}}},
        ),
        (
            [{"loc": ("a", "b", "c"), "msg": "message", "type": "value_error.str.regex"}],
            {"a": {"b": {"c": {"msg": "message", "type": "value_error.str.regex"}}}},
        ),
    ],
)
def test_pydantic_format_errors(data_input: list["ErrorDict"], data_output: dict[str, dict[str, typing.Any]]) -> None:
    """Test that output matches func(input)."""
    result = utils.pydantic_format_errors(data_input)
    assert result == data_output


@pytest.mark.asyncio
async def test_flash_messages() -> None:
    """Assert that flash messages can be created and displayed."""
    alert_input_list = [
        ("This is test message: info", utils.FlashLevel.INFO),
        ("This is test message: error", utils.FlashLevel.ERROR),
    ]

    @app.get("/test-append-flash-message/")
    async def append_flash_messaging(request: Request) -> dict[str, str]:
        for message, level in alert_input_list:
            utils.Flash.add_message(request, message, level=level)
        return {"result": "Ok"}

    @app.get("/test-fetch-flash-message/")
    async def fetch_flash_messaging(request: Request) -> dict[str, typing.Any]:
        return {"result": utils.Flash.get_messages(request)}

    async with TestClient(app) as client:
        response = await client.get("/test-fetch-flash-message/")
        assert response.json()["result"] == []

        await client.get("/test-append-flash-message/")

        response = await client.get("/test-fetch-flash-message/")
        alert_output_list = response.json()["result"]

    for alert_input, alert_output in zip(alert_input_list, alert_output_list):
        assert alert_input[0] == alert_output["message"]
        assert alert_input[1].value == alert_output["level"]
