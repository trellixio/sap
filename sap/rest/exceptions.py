"""
# Exceptions.

Known exceptions that can occur while using the app.
"""


import typing

# ---------------------------------------
# --------- Rest API ERROR -------------
# ---------------------------------------

# Those errors are returned by the Rest API


class RestAPIError(Exception):
    """Base Rest API error."""

    code: int = 0
    message: str = ""
    data: typing.Optional[dict[str, str]] = None

    def __repr__(self) -> str:
        """Display a string representation of the object."""
        return f"<{self.__class__.__name__}: {self.message}>"

    def __str__(self) -> str:
        """Display a string representation of the error."""
        return str(self.message)

    def __init__(self, *args: object, data: typing.Optional[dict[str, typing.Any]] = None) -> None:
        """Add error data."""
        super().__init__(*args)
        self.data = data

        if not data:
            return

        # verify if `error` is in data and if it is not empty
        if error_ := data.get("error"):
            if isinstance(error_, str):
                self.message = error_
            elif isinstance(error_, list) and isinstance(error_[0], str):
                self.message = ". ".join(error_)
            elif isinstance(error_, dict) and "message" in error_:
                self.message = error_["message"]

        # verify if `message` is in data and if it is not empty
        if message_ := data.get("message"):
            if isinstance(message_, str):
                self.message = message_


class Rest400Error(RestAPIError):
    """Data invalid."""

    code = 400
    message = "Invalid data"


class Rest401Error(RestAPIError):
    """Access token declined."""

    code = 401
    message = "Authentication refused."


class Rest403Error(RestAPIError):
    """Insufficient permission to access the requested data."""

    code = 403
    message = "Permission error."


class Rest404Error(RestAPIError):
    """Path or object does not exist."""

    code = 404
    message = "Data not found."


class Rest405Error(RestAPIError):
    """The method is not allowed is on this path."""

    code = 405
    message = "Method or path not allowed."


class Rest409Error(RestAPIError):
    """There was a conflict due to a duplicate transaction."""

    code = 409
    message = "Conflict or duplicate transaction."


class Rest503Error(RestAPIError):
    """The Rest server is down."""

    code = 503
    message = "The Rest server is unreachable."


RestErrorMap = {
    400: Rest400Error,
    422: Rest400Error,
    401: Rest401Error,
    403: Rest403Error,
    404: Rest404Error,
    405: Rest405Error,
    409: Rest409Error,
    # Server Error
    500: Rest503Error,
    501: Rest503Error,
    502: Rest503Error,
    503: Rest503Error,
}
