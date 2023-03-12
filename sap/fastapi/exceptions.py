from fastapi.exceptions import HTTPException


class Object404Error(HTTPException):
    """Raise when querying DB returns empty result"""

    status_code = 404
    detail = "Object not found"

    def __init__():
        pass
