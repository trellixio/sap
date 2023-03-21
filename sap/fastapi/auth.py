import time
import typing

import jwt

from fastapi import Cookie, Depends, Request, Response, status
from fastapi.exceptions import HTTPException

from AppMain.settings import AppSettings
from sap.beanie import Document

# from starlette.authentication import AuthenticationBackend


class JWTAuth:
    auth_login_url: typing.ClassVar[str] = "/pages/auth/login/"
    auth_cookie_key: typing.ClassVar[str] = "user_session"
    auth_cookie_expires: typing.ClassVar[int] = 60 * 60 * 12  # expiration = 12 hours

    @classmethod
    def get_auth_login_url(cls) -> str:
        """Retrieve the login url where user are redirect in case of auth failure."""
        return cls.auth_login_url

    @classmethod
    def get_auth_cookie_key(cls) -> str:
        """Retrieve key used to define the authentication cookie."""
        return cls.auth_cookie_key

    @classmethod
    def get_auth_cookie_expires(cls) -> int:
        """Retrieve validity in seconds of the authentication cookie."""
        return cls.auth_cookie_expires

    @classmethod
    def create_token(cls, user: Document, expires: typing.Optional[int] = None) -> str:
        """Get JWT temporary token."""
        expires = cls.get_auth_cookie_expires() if expires is None else expires
        jwt_data = {"exp": int(time.time()) + expires, "user_id": str(user.id)}
        return jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

    @classmethod
    async def find_user(cls, jwt_token: str, user_model_class: type[Document]) -> Document:
        """
        Verify that JWT token is valid.

        :param jwt_token: The lifespan of the token in seconds.
        :param user_model_class: user model class
        """
        jwt_data = jwt.decode(jwt_token, key=AppSettings.CRYPTO_SECRET, algorithms=["HS256"])
        # Raises: jwt.exceptions.InvalidTokenError => Token has expired or is invalid

        user = await user_model_class.find_one_or_404(
            user_model_class.id == jwt_data["user_id"],
            user_model_class.is_active == True,
        )
        # Raise: Object404Error => User cannot be found

        return user

    @classmethod
    async def login(cls, response: Response, user: Document) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.set_cookie(key=cls.get_auth_cookie_key(), value=cls.create_token(user=user), httponly=True)
        return response

    @classmethod
    async def logout(cls, response: Response) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.delete_cookie(key=cls.get_auth_cookie_key(), httponly=True)
        return response

    @classmethod
    def depends(cls, user_model_class: type[Document]) -> typing.Any:
        """Provide the authenticated user to views that require it."""

        async def retrieve_user(
            request: Request, jwt_cookie: str = Cookie(default="", alias=cls.get_auth_cookie_key())
        ) -> "Document":
            user = None
            if jwt_cookie:
                try:
                    jwt_data = jwt.decode(jwt_cookie, key=AppSettings.CRYPTO_SECRET, algorithms=["HS256"])
                except jwt.exceptions.InvalidTokenError:  # pragma: no cover
                    pass
                else:
                    user = await user_model_class.get(jwt_data["user_id"])
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers={"Location": cls.get_auth_login_url()}
                )
            return user

        return Depends(retrieve_user)
