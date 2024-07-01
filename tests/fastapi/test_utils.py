"""
Test Utils.

Test xlib.utils functions.
"""

import typing

import pytest
from async_asgi_testclient import TestClient

from fastapi import Request
from fastapi.datastructures import FormData

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


@pytest.mark.parametrize(
    ("data_input", "data_output"),
    [
        (
            FormData({"user[first_name]": "John", "user[last_name]": "Doe", "middle_name": "Moi"}),
            {"user": {"first_name": "John", "last_name": "Doe"}, "middle_name": "Moi"},
        ),
        (
            FormData([("users[]", "John"), ("users[]", "Doe"), ("middle_name", "Moi")]),
            {"users": ["John", "Doe"], "middle_name": "Moi"},
        ),
        (
            FormData([("user[names[]]", "John"), ("user[names[]]", "Doe"), ("middle_name", "Moi")]),
            {"user": {"names": ["John", "Doe"]}, "middle_name": "Moi"},
        ),
        (
            FormData([("user[name[pos_1]]", "John"), ("user[name[pos_2]]", "Doe"), ("middle_name", "Moi")]),
            {"user": {"name": {"pos_1": "John", "pos_2": "Doe"}}, "middle_name": "Moi"},
        ),
    ],
)
def test_unflatten_form_data(data_input: typing.Mapping[str, typing.Any], data_output: dict[str, typing.Any]) -> None:
    """Test that output matches func(input)."""
    result = utils.unflatten_form_data(data_input)
    assert result == data_output


@pytest.mark.parametrize(
    ("on_conflict", "dict_a", "dict_b", "data_output"),
    [
        (
            "override",
            {"key_1": "John", "key_2": "Doe", "key_3": "Moi"},
            {"key_2": "Raphael", "key_4": "Sud"},
            {"key_1": "John", "key_2": "Raphael", "key_3": "Moi", "key_4": "Sud"},
        ),
        (
            "override",
            {"key_1": "John", "key_2": ["Doe"], "key_3": ["Moi"]},
            {"key_2": "Raphael", "key_4": "Sud"},
            {"key_1": "John", "key_2": "Raphael", "key_3": ["Moi"], "key_4": "Sud"},
        ),
        (
            "merge",
            {"key_1": "John", "key_2": ["Doe"], "key_3": ["Moi"]},
            {"key_2": "Raphael", "key_4": "Sud"},
            {"key_1": "John", "key_2": ["Doe", "Raphael"], "key_3": ["Moi"], "key_4": "Sud"},
        ),
        (
            "override",
            {"key_1": "John", "key_2": {"key_21": "Jacques", "key_22": "Roy"}, "key_3": ["Moi"]},
            {"key_2": {"key_21": "Xavier"}, "key_4": "Sud"},
            {"key_1": "John", "key_2": {"key_21": "Xavier", "key_22": "Roy"}, "key_3": ["Moi"], "key_4": "Sud"},
        ),
    ],
)
def test_merge_dict_deep(
    on_conflict: str,
    dict_a: typing.Mapping[str, typing.Any],
    dict_b: typing.Mapping[str, typing.Any],
    data_output: dict[str, typing.Any],
) -> None:
    """Test that output matches func(input)."""
    result = utils.merge_dict_deep(dict_a, dict_b, on_conflict=on_conflict)
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
