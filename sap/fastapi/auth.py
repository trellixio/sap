"""
Auth.

Utils to handle user authentication and permissions.
"""
import base64
import binascii
import time
import typing
import warnings

import jwt

from fastapi import Cookie, Depends, Request, Response
from starlette.status import HTTP_401_UNAUTHORIZED as HTTP_401, HTTP_307_TEMPORARY_REDIRECT as HTTP_307
from fastapi.exceptions import HTTPException
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError, BaseUser
from starlette.requests import HTTPConnection

from AppMain.settings import AppSettings
from sap.beanie import Document
from sap.beanie.exceptions import Object404Error

UserT = typing.TypeVar("UserT", bound=Document)


class JWTAuth:
    """JWT cookie authentication utils.

    This can be used to login/logout user with persistent sessions.
    Mainly useful for Web Apps. For API, it is better to use Basic Authentication in Headers.
    """

    auth_login_url: typing.ClassVar[str] = "/pages/auth/login/"
    auth_cookie_key: typing.ClassVar[str] = "user_session"
    auth_cookie_expires: typing.ClassVar[int] = 60 * 60 * 12  # expiration = 12 hours
    user_model: type[Document]

    def __init__(self, user_model: type[UserT]) -> None:
        """Initialize the JWT auth helper.

        :param user_model: The User model class.
        """
        super().__init__()
        self.user_model = user_model

    def get_auth_login_url(self) -> str:
        """Retrieve the login url where user are redirect in case of auth failure."""
        return self.auth_login_url

    def get_auth_cookie_key(self) -> str:
        """Retrieve key used to define the authentication cookie."""
        return self.auth_cookie_key

    def get_auth_cookie_expires(self) -> int:
        """Retrieve validity in seconds of the authentication cookie."""
        return self.auth_cookie_expires

    def create_token(self, user: UserT) -> str:
        """Get JWT temporary token."""
        expires = self.get_auth_cookie_expires()
        jwt_data = {"exp": int(time.time()) + expires, "user_id": str(user.id)}
        return jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

    async def find_user(self, jwt_token: str) -> Document:
        """
        Verify that JWT token is valid.

        :param jwt_token: The lifespan of the token in seconds.
        """

        # Raises: jwt.exceptions.InvalidTokenError => Token has expired or is invalid
        jwt_data = jwt.decode(jwt_token, key=AppSettings.CRYPTO_SECRET, algorithms=["HS256"])
        if "user_id" not in jwt_data:
            raise jwt.exceptions.InvalidAudienceError("Cannot read user_id.")

        # Raises: Object404Error => User cannot be found
        return await self.user_model.get_or_404(jwt_data["user_id"])

    async def login(self, response: Response, user: UserT) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.set_cookie(
            key=self.get_auth_cookie_key(),
            value=self.create_token(user=user),
            httponly=True,
        )
        return response

    async def logout(self, response: Response) -> Response:
        """Create a persistent cookie based session for the authenticated user."""
        response.delete_cookie(key=self.get_auth_cookie_key(), httponly=True)
        return response

    def depends(self) -> typing.Any:
        """Provide the authenticated user to views that require it."""

        warnings.warn(
            "`jwt_auth.depends()` has been deprecated. Use `Depends(jwt_auth.authenticate())` instead",
            DeprecationWarning,
            stacklevel=2,
        )

        async def retrieve_user(jwt_token: str = Cookie(default="", alias=self.get_auth_cookie_key())) -> UserT:
            try:
                return await self.find_user(jwt_token=jwt_token)
            except (Object404Error, jwt.exceptions.InvalidTokenError) as exc:
                raise HTTPException(HTTP_307, headers={"Location": self.get_auth_login_url()}) from exc

        return Depends(retrieve_user)

    async def authenticate(self, request: Request) -> UserT:
        """Provide the authenticated user to views that require it."""
        try:
            jwt_token = request.cookies[self.get_auth_cookie_key()]
            return await self.find_user(jwt_token=jwt_token)
        except (KeyError, Object404Error, jwt.exceptions.InvalidTokenError) as exc:
            raise HTTPException(HTTP_307, headers={"Location": self.get_auth_login_url()}) from exc


class JWTAuthBackend(AuthenticationBackend, JWTAuth):
    """Starlette Backend to authenticate use through JWT Token in Cookies."""

    async def authenticate(self, conn: HTTPConnection) -> typing.Optional[typing.Tuple["AuthCredentials", "BaseUser"]]:
        """Authenticate the user using Cookies."""
        if self.get_auth_cookie_key() not in conn.cookies:
            return None

        jwt_cookie = conn.cookies[self.get_auth_cookie_key()]

        try:
            jwt_data = jwt.decode(jwt_cookie, key=AppSettings.CRYPTO_SECRET, algorithms=["HS256"])
        except jwt.exceptions.InvalidTokenError as exc:
            raise AuthenticationError("Invalid JWT token") from exc

        user = await self.user_model.get_or_404(jwt_data["user_id"])

        return AuthCredentials([user.get_scopes()]), user


class BasicAuth:
    """Basic authentication utils.

    This can be used to authenticate user with through `Authorization` header using the Basic protocol.
    Mainly useful for API access. For web app, check JWTAuth which support persistent cookie session.
    """

    user_model: type[Document]
    auth_key_attribute: typing.ClassVar[str] = "auth_key"

    def __init__(self, user_model: type[UserT]) -> None:
        """Initialize the auth helper.

        :param user_model: The User model class.
        """
        super().__init__()
        self.user_model = user_model

    def get_auth_key_attribute(self) -> typing.Optional[str]:
        """Retrieve name of the `auth_key` attribute use to verify user."""
        return self.auth_key_attribute

    async def authenticate(self, request: Request) -> UserT:
        """Provide the authenticated user to views that require it."""

        header_auth: str = request.headers.get("Authorization")
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

        if auth_key_name:=self.get_auth_key_attribute():
            auth_key = getattr(self.user_model, auth_key_name)
        else: 
            auth_key = None

        try:
            if auth_key:
                return await self.user_model.find_one_or_404(auth_key == user_key)
            else:
                return await self.user_model.get_or_404(user_key)
        except (Object404Error, jwt.exceptions.InvalidTokenError) as exc:
            raise HTTPException(HTTP_401, detail="Invalid basic auth credentials") from exc

