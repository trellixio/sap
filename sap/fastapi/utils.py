"""
# Helpers.

This file helps you centralized utility functions and classes
that needs to be re-used but are not a core part of the app logic.
"""

import base64
import re
from enum import Enum
from typing import TYPE_CHECKING, Any, Mapping, Optional

from fastapi import Request

if TYPE_CHECKING:
    from pydantic.error_wrappers import ErrorDict


def pydantic_format_errors(error_list: list["ErrorDict"]) -> dict[str, dict[str, Any]]:
    """Format pydantic ErrorDict with listed loc to dict format.

    [{'loc': ('a', 'b'), 'msg': 'message', 'type': 'value_error.str.regex'}]
    =>
    {'a': {'b': {'msg': 'message', 'type': 'value_error.str.regex'}}}
    """
    result = {}

    for error in error_list:
        loc = error["loc"]
        error_dict: dict[str, Any] = {"msg": error["msg"], "type": error["type"]}
        if "ctx" in error:
            error_dict["ctx"] = error["ctx"]
        for x in loc[:0:-1]:
            error_dict = {str(x): error_dict}
        result[str(loc[0])] = error_dict

    return result


class FlashLevel(Enum):
    """Fash message levels."""

    INFO: str = "info"
    ERROR: str = "error"
    SUCCESS: str = "success"


class Flash:
    """Toast messaging backend.

    Good applications and user interfaces are all about feedback.
    If the user does not get enough feedback they will probably end up hating the application.
    This provides a really simple way to give feedback to a user with the flashing system.
    The flashing system basically makes it possible to record a message at the end of a request
    and access it next request and only next request.

    This is based on https://flask.palletsprojects.com/en/2.2.x/patterns/flashing/
    """

    @classmethod
    def add_message(cls, request: Request, message: str, level: FlashLevel = FlashLevel.INFO) -> None:
        """Record a message to be displayed to the user."""
        if "_messages" not in request.session:
            request.session["_messages"] = []
        request.session["_messages"].append({"message": message, "level": level.value})

    @classmethod
    def get_messages(cls, request: Request) -> list[str]:
        """Get flashed messages in the template."""
        messages: list[str] = []
        if "_messages" in request.session:
            messages = request.session.pop("_messages")
            request.session["_messages"] = []
        return messages


def base64_url_encode(text: str) -> str:
    """Encode a b64 for use in URL query by removing `=` character."""
    return base64.urlsafe_b64encode(text.encode()).rstrip(b"\n=").decode("ascii")


def base64_url_decode(text: str) -> str:
    """Decode a URL safely encoded b64."""
    return base64.urlsafe_b64decode(text.encode().ljust(len(text) + len(text) % 4, b"=")).decode()


def merge_dict_deep(dict_a: dict[str, Any], dict_b: dict[str, Any], path: Optional[list[str]] = None) -> dict[str, Any]:
    """
    Deep merge dictionaries. Merge b into a.

    ```python
        a = {1:{"a":{A}}, 2:{"b":{B}}}
        b = {2:{"c":{C}}, 3:{"d":{D}}}

        print(merge_dict_deep(a, b))

        # result
        {1:{"a":{A}}, 2:{"b":{B},"c":{C}}, 3:{"d":{D}}}
    ```
    """
    # source: https://stackoverflow.com/questions/7204805/how-to-merge-dictionaries-of-dictionaries/7205107#7205107
    if path is None:
        path = []
    for key in dict_b:
        if key in dict_a:
            if isinstance(dict_a[key], dict) and isinstance(dict_b[key], dict):
                merge_dict_deep(dict_a[key], dict_b[key], path + [str(key)])
            elif dict_a[key] == dict_b[key]:
                pass  # same leaf value
            else:  # b value is more recent
                dict_a[key] = dict_b[key]
        else:
            dict_a[key] = dict_b[key]
    return dict_a


unflatten_regex = re.compile(r"(?P<key_parent>\w+)\[(?P<key_child>\w+)\]")


def unflatten_form_data(form_data: Mapping[str, Any]) -> dict[str, Any]:
    """
    Un-flatten a form data and return the corresponding cascading dict.

    ```python
    form_data = { "user[first_name]": "John", "user[last_name]": "Doe"}

    print(restructure_form_data(form_data))
    ```

    The result will be:
    ```python
        { "user": {"first_name": "John", "last_name": "Doe"}}
    ```
    """
    res: dict[str, Any] = {}

    for key, value in form_data.items():
        if reg_match := unflatten_regex.match(key):
            key_parent, key_child = reg_match.groups()
            res.setdefault(key_parent, {})
            res[key_parent][key_child] = value
        else:
            res[key] = value

    return res
