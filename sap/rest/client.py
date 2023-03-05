"""
Rest API Wrapper.

This is a wrapper for any API of type RESTful.
Use this wrapper to perform API requests with a REST app.

Learn more about REST: https://en.wikipedia.org/wiki/Representational_state_transfer
"""

import typing
import urllib.parse

import httpx

from sap.loggers import logger

from . import exceptions


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

    def __init__(self, basic_username: str = "", basic_password: str = "") -> None:
        """Initialize the API client."""
        self.basic_username = basic_username
        self.basic_password = basic_password

    async def get(self, path: str, *, params: typing.Optional[dict[str, typing.Union[str, int]]] = None) -> RestData:
        """Retrieve an object."""
        return await self.request("GET", path, params=params)

    async def post(
        self,
        path: str,
        *,
        json: typing.Optional[dict[str, typing.Any]] = None,
        files: typing.Optional[list[tuple[str, tuple[str, bytes, str]]]] = None,
    ) -> RestData:
        """Create an object."""
        return await self.request("POST", path, json=json, files=files)

    async def put(self, path: str, *, json: dict[str, typing.Any]) -> RestData:
        """Update an object."""
        return await self.request("PUT", path, json=json)

    async def delete(self, path: str, *, json: typing.Optional[dict[str, typing.Any]] = None) -> RestData:
        """Remove an object."""
        return await self.request("DELETE", path, json=json)

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
    ) -> RestData:
        """Perform an HTTPS request on the Rest API."""
        url: str = path if "://" in path else urllib.parse.urljoin(self.base_url, path)

        async with self._get_client() as client:
            response = await client.request(method, url, json=json, params=params, files=files)

        return await self.get_response_data(response)

    @staticmethod
    async def get_response_data(response: httpx.Response) -> RestData:
        """Extract data from Rest API response and raise exceptions when applicable."""
        response_data = RestData()

        if "application/json" in response.headers.get("content-type", ""):
            response_data = RestData(response.json())

        response_data.response = response
        if response.status_code >= 300:
            logger.debug("Bad response from Rest API code=%d data=%s", response.status_code, str(response_data))

        if response.status_code >= 500:  # pragma: no cover
            raise exceptions.Rest503Error(data=response_data)
        if response.status_code == 404:
            if "text/html" in response.headers["content-type"]:
                raise exceptions.Rest405Error(data=response_data)
            raise exceptions.Rest404Error(data=response_data)
        if response.status_code in exceptions.RestErrorMap:
            raise exceptions.RestErrorMap[response.status_code](data=response_data)

        response.raise_for_status()

        return response_data


class BeansClient(RestClient):
    """Async Beans API Client.

    An async wrapper around the Beans API.
    Common errors are handled by the wrapper.
    """

    base_url: str = "https://api.trybeans.com/v3/"

    def __init__(self, access_token: str) -> None:
        """Initialize the API client."""
        super().__init__(basic_username=access_token)

    @classmethod
    async def get_access_token(cls, code: str, beans_public: str, beans_secret: str) -> RestData:
        """Retrieve access_token to be use to perform API request on behalf on a merchant."""
        async with httpx.AsyncClient(auth=httpx.BasicAuth(beans_public, beans_secret)) as client:
            response = await client.get(urllib.parse.urljoin(cls.base_url, f"core/auth/integration_key/{code}"))
        integration_key = await cls.get_response_data(response)

        if isinstance(integration_key["card"], dict):  # making the code future proof with the upcoming API update
            integration_key["card"] = integration_key["card"]["id"]

        return integration_key
