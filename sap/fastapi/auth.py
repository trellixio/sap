"""
Auth.

Utils to handle user authentication and permissions.
"""

from __future__ import annotations

import base64
import binascii
import time
from typing import ClassVar, Generic, TypeVar, Union

import jwt

from fastapi import Request, Response
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

# from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, BaseUser
# from starlette.requests import HTTPConnection
from starlette.status import HTTP_303_SEE_OTHER as HTTP_303
from starlette.status import HTTP_401_UNAUTHORIZED as HTTP_401

from sap.beanie.document import Document
from sap.exceptions import Object404Error

UserT = TypeVar("UserT", bound=Document)
# UserViewT: typing_extensions.TypeAlias = Union[Document, BaseModel, object]
UserViewT = TypeVar("UserViewT", bound=Union[Document, BaseModel, object])


class JWTAuth:
    """JWT cookie authentication utils.

    This can be used to login/logout user with persistent sessions.
    Mainly useful for Web Apps. For API, it is better to use Basic Authentication in Headers.
    """

    auth_login_url: ClassVar[str] = "/pages/auth/login/"
    auth_cookie_key: ClassVar[str] = "user_session"
    auth_cookie_expires: ClassVar[int] = 60 * 60 * 12  # expiration = 12 hours
    crypto_secret: ClassVar[str] = "xxx-xxxxxxxxx-xxxxxx"
    user_model: type[Document]

    def __init__(self, user_model: type[UserT]) -> None:
        """Initialize the JWT auth helper.

        :param user_model: The User model class.
        """
        super().__init__()
        self.user_model = user_model

    def get_auth_login_url(self, request: Request) -> str:
        """Retrieve the login url where user are redirect in case of auth failure."""
        return self.auth_login_url

    def get_auth_cookie_key(self, request: Request) -> str:
        """Retrieve key used to define the authentication cookie."""
        return self.auth_cookie_key

    def get_auth_cookie_expires(self) -> int:
        """Retrieve validity in seconds of the authentication cookie."""
        return self.auth_cookie_expires

    def create_token(self, user: UserT) -> str:
        """Get JWT temporary token."""
        expires = self.get_auth_cookie_expires()
        jwt_data = {"exp": int(time.time()) + expires, "user_id": str(user.id)}
        return jwt.encode(payload=jwt_data, key=self.crypto_secret, algorithm="HS256")

    async def find_user(self, jwt_token: str) -> Document:
        """
        Verify that JWT token is valid.

        :param jwt_token: The lifespan of the token in seconds.
        """

        # Raises: jwt.exceptions.InvalidTokenError => Token has expired or is invalid
        jwt_data = jwt.decode(jwt_token, key=self.crypto_secret, algorithms=["HS256"])
        if "user_id" not in jwt_data:
            raise jwt.exceptions.InvalidAudienceError("Cannot read user_id.")

        # Raises: Object404Error => User cannot be found
        return await self.user_model.get_or_404(jwt_data["user_id"])

    async def login(self, response: Response, request: Request, user: UserT) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.set_cookie(
            key=self.get_auth_cookie_key(request),
            value=self.create_token(user=user),
            httponly=True,
        )
        return response

    async def logout(self, response: Response, request: Request) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.delete_cookie(key=self.get_auth_cookie_key(request), httponly=True)
        return response

    async def authenticate(self, request: Request) -> UserT:
        """Provide the authenticated user to views that require it."""
        try:
            jwt_token = request.cookies[self.get_auth_cookie_key(request)]
        except KeyError as exc:
            raise HTTPException(HTTP_303, headers={"Location": self.get_auth_login_url(request)}) from exc

        try:
            return await self.find_user(jwt_token=jwt_token)
        except (Object404Error, jwt.exceptions.InvalidTokenError) as exc:
            raise HTTPException(HTTP_303, headers={"Location": self.get_auth_login_url(request)}) from exc


# class JWTAuthBackend(AuthenticationBackend, JWTAuth):
#     """Starlette Backend to authenticate use through JWT Token in Cookies."""

#     async def authenticate(self, request: HTTPConnection) -> UserT:
#         """Authenticate the user using Cookies."""
#         cookie_key: str = self.get_auth_cookie_key(request=request)
#         if cookie_key not in request.cookies:
#             raise AuthenticationError("Unable to find JWT cookie")

#         jwt_cookie = request.cookies[cookie_key]

#         try:
#             jwt_data = jwt.decode(jwt_cookie, key=self.crypto_secret, algorithms=["HS256"])
#         except jwt.exceptions.InvalidTokenError as exc:
#             raise AuthenticationError("Invalid JWT token") from exc

#         user = await self.user_model.get_or_404(jwt_data["user_id"])

#         return user
#         # return AuthCredentials([user.get_scopes()]), user


class BasicAuth(Generic[UserViewT]):
    """Basic authentication utils.

    This can be used to authenticate user with through `Authorization` header using the Basic protocol.
    Mainly useful for API access. For web app, check JWTAuth which support persistent cookie session.
    """

    user_model: type[UserViewT] | None
    auth_key_attribute: ClassVar[str] = "auth_key"

    def __init__(self, user_model: type[UserViewT] | None = None) -> None:
        """Initialize the auth helper.

        :param user_model: The User model class.
        """
        super().__init__()
        self.user_model = user_model

    def get_auth_key_attribute(self) -> str | None:
        """Retrieve name of the `auth_key` attribute use to verify user."""
        return self.auth_key_attribute

    async def retrieve_user(
        self, user_key: str, pwd: str | None = None  # pylint: disable=unused-argument
    ) -> UserViewT:
        """Retrieve a user using authorization key."""
        if self.user_model and issubclass(self.user_model, Document):
            if auth_key_name := self.get_auth_key_attribute():
                auth_key = getattr(self.user_model, auth_key_name)
                return await self.user_model.find_one_or_404(auth_key == user_key)

            return await self.user_model.get_or_404(user_key)
        raise NotImplementedError

    async def authenticate(self, request: Request) -> UserViewT:
        """Provide the authenticated user to views that require it."""

        header_auth: str | None = request.headers.get("Authorization")
        if not header_auth:
            raise HTTPException(HTTP_401, detail="Authentication required")

        scheme, credentials = header_auth.split()
        if scheme.lower() != "basic":
            raise HTTPException(HTTP_401, detail="Only basic authorization is supported")

        try:
            decoded = base64.b64decode(credentials).decode("ascii")
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise HTTPException(HTTP_401, detail="Error while decoding basic auth credentials") from exc

        username, _, pwd = decoded.partition(":")
        user_key = username or pwd

        try:
            return await self.retrieve_user(user_key, pwd=pwd)
        except (Object404Error, jwt.exceptions.InvalidTokenError) as exc:
            raise HTTPException(HTTP_401, detail="Invalid basic auth credentials") from exc
