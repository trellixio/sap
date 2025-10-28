# pylint: disable=too-many-arguments, too-many-positional-arguments

"""REST testing library utils."""

from __future__ import annotations

import typing
from base64 import b64encode

from async_asgi_testclient import TestClient
from requests.models import Response

from fastapi import status

from AppMain.asgi import app
from sap.beanie.document import DocT
from sap.fastapi.pagination import PaginatedResponse
from sap.fastapi.user import UserMixin

if typing.TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict


class Headers(typing.TypedDict, total=False):
    """Format Request headers."""

    Authorization: str


async def get_headers(user: UserMixin) -> Headers:
    """Get default headers for api authentication."""
    auth_key = await user.get_auth_key()
    basic_auth = b64encode((f"{auth_key}:").encode("utf-8")).decode("ascii")
    headers: Headers = {"Authorization": f"Basic {basic_auth}"}
    return headers


async def assert_response_forbidden(response: Response) -> bool:
    """Check that a request was rejected to due to lack sufficient authorization."""
    assert response.status_code in [
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
        # status.HTTP_404_NOT_FOUND,
        status.HTTP_405_METHOD_NOT_ALLOWED,
    ], response.content

    return True


async def assert_rest_can_list(
    base_url: str,
    sample: typing.Optional[dict[str, typing.Any]] = None,
    user: typing.Optional[UserMixin] = None,
    roles: typing.Optional[list[str]] = None,
) -> bool:
    """Retrieve an item through its ID."""
    headers = await get_headers(user) if user else {}

    async with TestClient(app, headers=headers) as client:
        response = await client.get(base_url)

    async def assert_response_authorized() -> bool:
        """Verify that the action was successfully performed."""

        assert response.status_code == status.HTTP_200_OK, response.content
        assert sample

        # Ensure that the response data has the right format
        # Ensure that the output data matches the input
        response_data: PaginatedResponse = response.json()

        # from rich import print
        # print(response_data)

        assert sample.keys() == response_data["data"][0].keys()

        return True

    if roles is None or (user and user.role in roles):
        # roles is None => Can perform action without authentication
        # user.role in roles => Authenticated user can perform action if they have permission
        return await assert_response_authorized()

    return await assert_response_forbidden(response)


async def assert_rest_can_retrieve(
    base_url: str,
    item_id: str,
    sample: typing.Optional[dict[str, typing.Any]] = None,
    user: typing.Optional[UserMixin] = None,
    roles: typing.Optional[list[str]] = None,
) -> bool:
    """Retrieve an item through its ID."""
    headers = await get_headers(user) if user else {}

    async with TestClient(app, headers=headers) as client:
        response = await client.get(f"{base_url}{item_id}/")

    async def assert_response_authorized() -> bool:
        """Verify that the action was successfully performed."""
        assert response.status_code == status.HTTP_200_OK, response.content
        assert sample

        # Ensure that the response data has the right format
        response_data: dict[str, typing.Any] = response.json()

        # from rich import print
        # print(response_data)

        assert (
            sample.keys() == response_data.keys()
        ), f"WrongObject expected={sample.keys()} received={response_data.keys()}"

        for key, value in sample.items():
            if value is None:
                continue
            assert type(value) == type(
                response_data[key]
            ), f"TypeMismatch key={key} expected={type(value)} received={type(response_data[key])}"
            if isinstance(value, dict):
                assert (
                    value.keys() == response_data[key].keys()
                ), f"WrongEmbeddedObject key={key} expected={value.keys()} received={response_data[key].keys()}"

        return True

    if roles is None or (user and user.role in roles):
        # roles is None => Can perform action without authentication
        # user.role in roles => Authenticated user can perform action
        return await assert_response_authorized()

    return await assert_response_forbidden(response)


async def assert_rest_can_create(
    base_url: str,
    sample: dict[str, typing.Any],
    variant_good: typing.Optional[dict[str, typing.Any]] = None,
    variant_bad: typing.Optional[dict[str, typing.Any]] = None,
    user: typing.Optional[UserMixin] = None,
    roles: typing.Optional[list[str]] = None,
) -> bool:
    """Update an item using its ID."""
    headers = await get_headers(user) if user else {}

    variant_good = variant_good or {}
    variant_bad = variant_bad or {}

    async with TestClient(app, headers=headers) as client:
        response_good = await client.post(base_url, json=sample | variant_good)
        response_bad = await client.post(base_url, json=sample | variant_bad)

    async def assert_response_authorized() -> bool:
        """Verify that the action was successfully performed."""
        assert variant_good
        assert variant_bad

        assert response_good.status_code == status.HTTP_201_CREATED, response_good.content
        assert response_bad.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response_bad.content

        # Ensure that the response data has the right format
        response_good_data: dict[str, typing.Any] = response_good.json()
        for key, value in variant_good.items():
            # some case are only accepted at creation for example admin_email when creating agency
            if key in response_good_data:
                error_message = f"Updating data failed {key=} expected={value} found={response_good_data[key]}"
                assert response_good_data[key] == value, error_message

        response_bad_data: dict[str, typing.Any] = response_bad.json()
        details: typing.Union[list["ErrorDict"], str] = response_bad_data["detail"]

        if isinstance(details, list):
            for key, value in variant_bad.items():
                error_message = (
                    f"Updating data was not rejected as expected {key=} {value=} receive={response_bad_data}"
                )
                assert any(key in detail["loc"] for detail in details), error_message

        return True

    if roles is None or (user and user.role in roles):
        # roles is None => Can perform action without authentication
        # user.role in roles => Authenticated user can perform action
        return await assert_response_authorized()

    return await assert_response_forbidden(response_good) and await assert_response_forbidden(response_bad)


async def assert_rest_can_update(
    base_url: str,
    item_id: str,
    variant_good: typing.Optional[dict[str, typing.Any]] = None,
    variant_bad: typing.Optional[dict[str, typing.Any]] = None,
    user: typing.Optional[UserMixin] = None,
    roles: typing.Optional[list[str]] = None,
) -> bool:
    """Update an item using its ID."""
    headers = await get_headers(user) if user else {}

    variant_good = variant_good or {}
    variant_bad = variant_bad or {}

    async with TestClient(app, headers=headers) as client:
        data_initial = (await client.get(f"{base_url}{item_id}/")).json()
        response_good = await client.put(f"{base_url}{item_id}/", json=data_initial | variant_good)
        response_bad = await client.put(f"{base_url}{item_id}/", json=data_initial | variant_bad)

    async def assert_response_authorized() -> bool:
        """Verify that the action was successfully performed."""
        assert variant_good
        assert variant_bad

        assert response_good.status_code == status.HTTP_202_ACCEPTED, response_good.content
        assert response_bad.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT, response_bad.content

        # Ensure that the response data has the right format
        response_good_data: dict[str, typing.Any] = response_good.json()
        for key, value in variant_good.items():
            error_message = f"Updating data failed {key=} expected={value} found={response_good_data[key]}"
            assert response_good_data[key] == value, error_message

        response_bad_data: dict[str, typing.Any] = response_bad.json()
        for key, value in variant_bad.items():
            details: list["ErrorDict"] = response_bad_data["detail"]
            error_message = f"Updating data was not rejected as expected {key=} {value=} receive={response_bad_data}"
            assert any(key in detail["loc"] for detail in details), error_message

        return True

    if roles is None or (user and user.role in roles):
        # roles is None => Can perform action without authentication
        # user.role in roles => Authenticated user can perform action
        return await assert_response_authorized()

    return await assert_response_forbidden(response_good) and await assert_response_forbidden(response_bad)


async def assert_rest_can_destroy(
    base_url: str,
    item_id: str,
    item: DocT,
    user: typing.Optional[UserMixin] = None,
    roles: typing.Optional[list[str]] = None,
) -> bool:
    """Delete an item."""
    headers = await get_headers(user) if user else {}

    async with TestClient(app, headers=headers) as client:
        response = await client.delete(f"{base_url}{item_id}/")

    async def assert_response_authorized() -> bool:
        """Verify that the action was successfully performed."""
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not await item.get(item_id)
        return True

    if roles is None or (user and user.role in roles):
        # roles is None => Can perform action without authentication
        # user.role in roles => Authenticated user can perform action
        return await assert_response_authorized()

    return await assert_response_forbidden(response)
