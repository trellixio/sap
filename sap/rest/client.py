"""
Rest API Wrapper.

This is a wrapper for any API of type RESTful.
Use this wrapper to perform API requests with a REST app.

Learn more about REST: https://en.wikipedia.org/wiki/Representational_state_transfer
"""

from __future__ import annotations

import typing
import urllib.parse

import httpx

from sap.loggers import logger

from . import rest_exceptions


class RestData(dict[str, typing.Any]):
    """A response data from a REST client request."""

    response: typing.Optional[httpx.Response] = None


class RestClient:
    """Async Rest API Client.

    An async wrapper around any Rest API.
    Common errors are handled by the wrapper.
    """

    basic_username: str = ""
    basic_password: str = ""
    base_url: str = ""
    response_cache: typing.Optional[httpx.Response] = None

    def __init__(self, basic_username: str = "", basic_password: str = "") -> None:
        """Initialize the API client."""
        self.basic_username = basic_username
        self.basic_password = basic_password

    async def get(
        self,
        path: str,
        *,
        params: typing.Optional[dict[str, typing.Any]] = None,
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Retrieve an object."""
        return await self.request("GET", path, params=params, headers=headers)

    async def post(
        self,
        path: str,
        *,
        json: typing.Optional[dict[str, typing.Any]] = None,
        files: typing.Optional[list[tuple[str, tuple[str, bytes, str]]]] = None,
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Create an object."""
        return await self.request("POST", path, json=json, files=files, headers=headers)

    async def put(
        self,
        path: str,
        *,
        json: dict[str, typing.Any],
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Update an object."""
        return await self.request("PUT", path, json=json, headers=headers)

    async def patch(
        self,
        path: str,
        *,
        json: dict[str, typing.Any],
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Patch an object."""
        return await self.request("PATCH", path, json=json, headers=headers)

    async def delete(
        self,
        path: str,
        *,
        json: typing.Optional[dict[str, typing.Any]] = None,
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Remove an object."""
        return await self.request("DELETE", path, json=json, headers=headers)

    def _get_client(self) -> httpx.AsyncClient:
        """Get retrieve client with headers."""
        auth = None
        if self.basic_username or self.basic_password:
            auth = httpx.BasicAuth(self.basic_username, self.basic_password)
        return httpx.AsyncClient(auth=auth)

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: typing.Optional[dict[str, typing.Any]] = None,
        params: typing.Optional[dict[str, typing.Union[str, int]]] = None,
        files: typing.Optional[list[tuple[str, tuple[str, bytes, str]]]] = None,
        headers: typing.Optional[dict[str, str]] = None,
    ) -> RestData:
        """Perform an HTTPS request on the Rest API."""
        url: str = path if "://" in path else urllib.parse.urljoin(self.base_url, path)

        async with self._get_client() as client:
            response = await client.request(method, url, json=json, params=params, files=files, headers=headers)

        logger.debug("%s, %s, %s", method, url, response)
        self.response_cache = response
        return await self.get_response_data(response)

    @staticmethod
    async def get_response_data(response: httpx.Response) -> RestData:
        """Extract data from Rest API response and raise exceptions when applicable."""
        res_json: typing.Union[dict[str, typing.Any], list[typing.Any]]

        try:
            res_json = response.json()
        except ValueError:
            res_json = {}

        if isinstance(res_json, dict):
            response_data = RestData(res_json)
        else:
            response_data = RestData({"data": res_json})

        response_data.response = response
        if response.status_code >= 300:
            logger.debug("Bad response from Rest API code=%d data=%s", response.status_code, str(response_data))

        if response.status_code >= 500:  # pragma: no cover
            raise rest_exceptions.Rest503Error(response=response, request=response.request, data=response_data)
        if response.status_code == 404:
            if "text/html" in response.headers["content-type"]:
                raise rest_exceptions.Rest405Error(response=response, request=response.request, data=response_data)
            raise rest_exceptions.Rest404Error(response=response, request=response.request, data=response_data)
        if response.status_code in rest_exceptions.REST_ERROR_MAP:
            raise rest_exceptions.REST_ERROR_MAP[response.status_code](
                response=response, request=response.request, data=response_data
            )

        response.raise_for_status()

        return response_data


class BeansClient(RestClient):
    """Async Beans API Client.

    An async wrapper around the Beans API.
    Common errors are handled by the wrapper.
    """

    base_url: str = "https://api.trybeans.com/v3/"

    def __init__(self, access_token: str | None) -> None:
        """Initialize the API client."""
        assert access_token is not None
        super().__init__(basic_username=access_token)

    @classmethod
    async def get_access_token(cls, code: str, beans_public: str, beans_secret: str) -> RestData:
        """Retrieve access_token to be use to perform API request on behalf on a merchant."""
        client = RestClient(beans_public, beans_secret)
        integration_key = await client.get(urllib.parse.urljoin(cls.base_url, f"core/auth/integration_key/{code}"))

        if isinstance(integration_key["card"], dict):  # making the code future proof with the upcoming API update
            integration_key["card"] = integration_key["card"]["id"]

        return integration_key
