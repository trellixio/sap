"""
Test REST Exceptions.

Test how REST error payloads are turned into messages.
"""

import typing

import httpx
import pytest

from sap.rest.rest_exceptions import RestAPIError


def rest_error(data: dict[str, typing.Any]) -> RestAPIError:
    """Build a REST error from a response payload."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(400, request=request)
    return RestAPIError(request=request, response=response, data=data)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"error": "bad"}, "bad"),
        ({"error": ["one", "two"]}, "one. two"),
        ({"error": {"message": "nope"}}, "nope"),
        ({"message": "hello"}, "hello"),
        ({"other": 1}, str({"other": 1})),
    ],
)
def test_rest_api_error_message(data: dict[str, typing.Any], message: str) -> None:
    """Parse error and message fields from a REST payload."""
    assert str(rest_error(data)) == message
