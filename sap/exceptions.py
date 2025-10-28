"""
# Exceptions.

Basic exceptions used across the sap package.
"""

from fastapi import HTTPException, status


class HTTPError(HTTPException):
    """Subclassing HTTPException."""

    status_code: int
    detail: str

    def __init__(self, detail: str = ""):
        """Init exception."""
        super().__init__(status_code=self.status_code, detail=detail or self.detail)


class Object404Error(HTTPError):
    """Raise when querying DB returns empty result."""

    status_code: int = 404
    detail: str = "Object not found"


class Validation422Error(HTTPError):
    """Raise when parameter validation fails."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_CONTENT
    detail: str = "The data submitted is invalid."


class Validation400Error(HTTPError):
    """Raise when data validation fails."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "The data submitted has been rejected."


class Permission403Error(HTTPError):
    """Not enough permission to access resource."""

    status_code: int = status.HTTP_403_FORBIDDEN
    detail: str = "Not enough permission to access resource."


class Cache404Error(HTTPError):
    """Raise when querying cache returns empty result."""

    status_code: int = 404
    detail: str = "Object not found in cache"


class Duplicate409Error(HTTPError):
    """A duplication unique transaction id."""

    status_code: int = 409
    detail: str = "Duplicate transaction."


__all__ = [
    "Object404Error",
    "Cache404Error",
    "Validation400Error",
    "Validation422Error",
    "Permission403Error",
    "Duplicate409Error",
]
