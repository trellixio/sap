from fastapi.exceptions import HTTPException


class Object404Error(HTTPException):
    """Raise when querying DB returns empty result"""

    status_code: int = 404
    detail: str = "Object not found"

    def __init__(self, detail: str = ""):
        self.detail = detail or self.detail
        pass
