# pylint: disable=too-many-arguments, protected-access, too-many-locals

"""
Utils.

Re-usable methods and functions for all test cases.
"""
from __future__ import annotations

import random
import string
from typing import Any

import httpx
from rich import print  # pylint: disable=redefined-builtin

from sap.rest.rest_exceptions import REST_ERROR_MAP


def generate_random_string(length: int) -> str:
    """Generate a random string of a given length."""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_random_email(domain: str = "yopmail.net", length: int = 9) -> str:
    """Get a random email to be using in test cases."""
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(length))
    return "trellis-test." + random_string + "@" + domain


class PytestState(dict[str, Any]):
    """Store a global state for the current batch of tests."""


CACHED_DATA: dict[str, dict[str, Any]] = {}


# def stringify_request_key(obj: Mapping[str, Any] | Mapping[bytes, Any] | Sequence[Any] | httpx.Headers | httpx.QueryParams | None) -> str:
def stringify_request_key(obj: Any) -> str:
    """Return a human readable string transformation of dict inspired by pytest parametrization."""
    if obj is None:
        return "None"
    items: list[str] = []
    for k, v in obj.items():
        if isinstance(v, dict):
            v_str = stringify_request_key(v)
        else:
            v_str = str(v)
        items.append(f"{k}_{v_str}")

    return "-".join(items)


original__https__request = httpx.AsyncClient.request


async def cache__httpx__request(
    self: httpx.AsyncClient,
    method: str,
    url: httpx._types.URLTypes,
    *,
    content: httpx._types.RequestContent | None = None,
    data: httpx._types.RequestData | None = None,
    files: httpx._types.RequestFiles | None = None,
    json: Any | None = None,
    params: httpx._types.QueryParamTypes | None = None,
    headers: httpx._types.HeaderTypes | None = None,
    cookies: httpx._types.CookieTypes | None = None,
    auth: httpx._types.AuthTypes | httpx._client.UseClientDefault | None = httpx._client.USE_CLIENT_DEFAULT,
    follow_redirects: bool | httpx._client.UseClientDefault = httpx._client.USE_CLIENT_DEFAULT,
    timeout: httpx._types.TimeoutTypes | httpx._client.UseClientDefault = httpx._client.USE_CLIENT_DEFAULT,
    extensions: httpx._types.RequestExtensions | None = None,
) -> httpx.Response:
    """Return cached request if exists otherwise perform HTTP request."""
    request = self.build_request(
        method=method,
        url=url,
        content=content,
        data=data,
        files=files,
        json=json,
        params=params,
        headers=headers,
        cookies=cookies,
        timeout=timeout,
        extensions=extensions,
    )

    request_key = ":".join(
        [
            method,
            str(url),
            str(content),
            stringify_request_key(data),
            str(files),
            stringify_request_key(json),
            stringify_request_key(params),
            stringify_request_key(headers),
        ]
    )

    if request_key in CACHED_DATA:
        result_cached: dict[str, Any] = CACHED_DATA[request_key]
        response = httpx.Response(**result_cached, request=request)
        if result_cached["status_code"] >= 400:
            raise REST_ERROR_MAP[result_cached["status_code"]](
                response=response, request=request, data=result_cached["json"]
            )
        return response

    print(f"NON-CACHED HTTPX REQUEST {request_key=} result=>")
    # breakpoint()
    response = await self.send(request, auth=auth, follow_redirects=follow_redirects)

    response_data: dict[str, Any] = {
        "status_code": response.status_code,
        # "headers": response.headers,
    }
    if response.content:
        if "application/json" in response.headers.get("content-type", ""):
            response_data["json"] = response.json()
        else:
            response_data["content"] = response.content
        print(response_data)
    return response
