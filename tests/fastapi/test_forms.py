"""
Test Forms.

Test form validation helpers.
"""

import typing
from urllib.parse import parse_qsl

import pytest

from fastapi import Request
from fastapi.datastructures import FormData

from sap.exceptions import Validation422Error
from sap.fastapi.forms import validate_form
from sap.fastapi.utils import FlashLevel
from tests.samples import DummyDoc, DummyDocSerializer, DummyDocWriteSerializer


def form_request(body: str) -> Request:
    """Build a POST request carrying urlencoded form data."""

    async def receive() -> dict[str, typing.Any]:
        """Return the request body once."""
        return {"type": "http.request", "body": body.encode(), "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/form/",
        "raw_path": b"/form/",
        "query_string": b"",
        "headers": [
            (b"content-type", b"application/x-www-form-urlencoded"),
            (b"content-length", str(len(body)).encode()),
        ],
        "client": ("127.0.0.1", 123),
        "server": ("127.0.0.1", 8000),
        "session": {},
    }
    request = Request(scope, receive)
    request._form = FormData(dict(parse_qsl(body)))  # pylint: disable=protected-access
    return request


def raising_serializer(error: Exception) -> type[DummyDocWriteSerializer]:
    """Build a write serializer that fails async validation."""

    class RaisingWriteSerializer(DummyDocWriteSerializer):
        """Write serializer that fails async validation."""

        async def run_async_validators(self, **kwargs: typing.Any) -> None:  # pylint: disable=no-self-use
            """Raise the configured validation error."""
            raise error

    return RaisingWriteSerializer


@pytest.mark.asyncio
async def test_validate_form_create() -> None:
    """Accept a valid form and return the write serializer."""
    request = form_request("num=7&name=Created&info[num]=1&info[name]=Emb&info[limit]=2")

    result = await validate_form(request, DummyDocWriteSerializer)

    assert result.errors == {}
    assert result.serializer is not None
    assert result.serializer.num == 7
    assert result.serializer.name == "Created"
    assert "_messages" not in request.session


@pytest.mark.asyncio
async def test_validate_form_update() -> None:
    """Merge submitted fields over the stored document."""
    doc = await DummyDoc.find_one_or_404()
    request = form_request("name=Updated+Name")

    result = await validate_form(request, DummyDocWriteSerializer, DummyDocSerializer, doc)

    assert result.errors == {}
    assert result.serializer is not None
    assert result.data["num"] == doc.num
    assert result.data["name"] == "Updated Name"
    assert result.serializer.name == "Updated Name"
    assert "_messages" not in request.session


@pytest.mark.asyncio
async def test_validate_form_pydantic_error() -> None:
    """Report field errors and a root message when the form is invalid."""
    request = form_request("name=OnlyName&info[num]=1&info[name]=Emb&info[limit]=2")

    result = await validate_form(request, DummyDocWriteSerializer)

    assert result.serializer is None
    assert "num" in result.errors
    assert result.errors["__root__"] == {"msg": "Please review submitted form."}
    assert request.session["_messages"] == [
        {"message": "Please review submitted form.", "level": FlashLevel.ERROR.value}
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [AssertionError("invalid form"), Validation422Error("invalid form")])
async def test_validate_form_async_error(error: Exception) -> None:
    """Surface async validator failures as a root form error."""
    request = form_request("num=7&name=Created&info[num]=1&info[name]=Emb&info[limit]=2")

    result = await validate_form(request, raising_serializer(error))

    assert result.serializer is None
    assert result.errors["__root__"] == {"msg": str(error)}
    assert request.session["_messages"] == [{"message": str(error), "level": FlashLevel.ERROR.value}]
