"""
Exceptions.

Group common logic exceptions such as ValidationError
"""

from fastapi import HTTPException, status

from sap.beanie.exceptions import Object404Error


class HTTPError(HTTPException):
    """Subclassing HTTPException."""

    status_code: int
    detail: str

    def __init__(self, detail: str = ""):
        """Init exception."""
        super().__init__(status_code=self.status_code, detail=detail or self.detail)


class Validation422Error(HTTPError):
    """Raise when parameter validation fails."""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail: str = "The data submitted is invalid."


class Validation400Error(HTTPError):
    """Raise when data validation fails."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "The data submitted has been rejected."


__all__ = [
    "Object404Error",
    "Validation400Error",
    "Validation422Error",
]
