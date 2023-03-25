from fastapi import HTTPException, status

from sap.beanie.exceptions import Object404Error as Object404Error


class Validation422Error(HTTPException):
    """Raise when querying DB returns empty result"""

    status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail: str = "The data submitted is invalid"

    def __init__(self, detail: str = ""):
        super().__init__(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail or self.detail)
