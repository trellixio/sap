"""
Exceptions.

Group exceptions specific to database error such as ObjectNotFound or IntegrityError
"""
from fastapi.exceptions import HTTPException


class Object404Error(HTTPException):
    """Raise when querying DB returns empty result."""

    status_code: int = 404
    detail: str = "Object not found"

    def __init__(self, detail: str = ""):
        """Init exception."""
        super().__init__(status_code=404, detail=detail or self.detail)
