# pylint: disable=no-self-use, protected-access
"""Tests for fastapi/auth.py."""

import base64
import time
import typing

import jwt
import pytest
import pytest_asyncio

from beanie import PydanticObjectId
from fastapi import Request, Response, status
from fastapi.exceptions import HTTPException

from AppMain.settings import AppSettings
from sap.exceptions import Object404Error
from sap.fastapi.auth import BasicAuth, JWTAuth
from tests.samples import UserDoc


class TestJWTAuth:
    """Test cases for JWTAuth class."""

    @pytest_asyncio.fixture
    async def user_doc(self) -> typing.AsyncGenerator[UserDoc, None]:
        """Create a test user document."""
        user = await UserDoc(username="testuser", email="test@example.com").create()
        user.set_password("testpassword123")
        await user.save()
        yield user
        await user.delete()

    @pytest.fixture
    def jwt_auth(self) -> JWTAuth:
        """Create a JWTAuth instance."""
        return JWTAuth(user_model=UserDoc)

    @pytest.fixture
    def mock_response(self) -> Response:
        """Create a mock Response object."""
        return Response(content="test")

    @pytest.mark.asyncio
    async def test_create_token(self, jwt_auth: JWTAuth, user_doc: UserDoc) -> None:
        """Test create_token generates valid JWT token."""
        token = jwt_auth.create_token(user_doc)

        # Decode the token to verify its contents
        decoded = jwt.decode(token, key=AppSettings.CRYPTO_SECRET, algorithms=["HS256"])

        assert "exp" in decoded
        assert "user_id" in decoded
        assert decoded["user_id"] == str(user_doc.id)

        # Verify expiration time is set correctly
        expected_exp = int(time.time()) + jwt_auth.get_auth_cookie_expires()
        assert abs(decoded["exp"] - expected_exp) < 5  # Allow 5 second tolerance

    @pytest.mark.asyncio
    async def test_find_user_success(self, jwt_auth: JWTAuth, user_doc: UserDoc) -> None:
        """Test find_user successfully retrieves user with valid token."""
        token = jwt_auth.create_token(user_doc)
        found_user = await jwt_auth.find_user(token)

        assert found_user.id == user_doc.id
        assert found_user.username == user_doc.username
        assert found_user.email == user_doc.email

    @pytest.mark.asyncio
    async def test_find_user_expired_token(self, jwt_auth: JWTAuth, user_doc: UserDoc) -> None:
        """Test find_user raises error with expired token."""
        # Create an expired token
        expired_time = int(time.time()) - 3600  # Expired 1 hour ago
        jwt_data = {"exp": expired_time, "user_id": str(user_doc.id)}
        expired_token = jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

        with pytest.raises(jwt.exceptions.InvalidTokenError):
            await jwt_auth.find_user(expired_token)

    @pytest.mark.asyncio
    async def test_find_user_invalid_token(self, jwt_auth: JWTAuth) -> None:
        """Test find_user raises error with invalid token."""
        with pytest.raises(jwt.exceptions.InvalidTokenError):
            await jwt_auth.find_user("invalid_token_string")

    @pytest.mark.asyncio
    async def test_find_user_missing_user_id(self, jwt_auth: JWTAuth) -> None:
        """Test find_user raises error when token lacks user_id."""
        # Create token without user_id
        jwt_data = {"exp": int(time.time()) + 3600}
        token = jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

        with pytest.raises(jwt.exceptions.InvalidAudienceError):
            await jwt_auth.find_user(token)

    @pytest.mark.asyncio
    async def test_find_user_nonexistent_user(self, jwt_auth: JWTAuth) -> None:
        """Test find_user raises error when user doesn't exist."""
        # Create token with non-existent user_id
        fake_id = PydanticObjectId()
        jwt_data = {"exp": int(time.time()) + 3600, "user_id": str(fake_id)}
        token = jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

        with pytest.raises(Object404Error):
            await jwt_auth.find_user(token)

    @pytest.mark.asyncio
    async def test_login(
        self, jwt_auth: JWTAuth, user_doc: UserDoc, request_basic: Request, mock_response: Response
    ) -> None:
        """Test login sets authentication cookie."""
        response = await jwt_auth.login(mock_response, request_basic, user_doc)

        # Verify cookie was set
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "user_session=" in cookie_header
        assert "HttpOnly" in cookie_header

    @pytest.mark.asyncio
    async def test_logout(self, jwt_auth: JWTAuth, request_basic: Request, mock_response: Response) -> None:
        """Test logout deletes authentication cookie."""
        response = await jwt_auth.logout(mock_response, request_basic)

        # Verify cookie was deleted
        assert "set-cookie" in response.headers
        cookie_header = response.headers["set-cookie"]
        assert "user_session=" in cookie_header
        assert "Max-Age=0" in cookie_header or "expires=" in cookie_header.lower()

    @pytest.mark.asyncio
    async def test_authenticate_success(self, jwt_auth: JWTAuth, user_doc: UserDoc, request_basic: Request) -> None:
        """Test authenticate returns user with valid cookie."""
        # Create token and set it in request cookies
        token = jwt_auth.create_token(user_doc)
        request_basic._cookies = {"user_session": token}

        user: UserDoc = await jwt_auth.authenticate(request_basic)

        assert user.id == user_doc.id
        assert user.username == user_doc.username

    @pytest.mark.asyncio
    async def test_authenticate_missing_cookie(self, jwt_auth: JWTAuth, request_basic: Request) -> None:
        """Test authenticate raises HTTPException when cookie is missing."""
        request_basic._cookies = {}

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.authenticate(request_basic)

        assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert exc_info.value.headers is not None
        assert exc_info.value.headers["Location"] == "/pages/auth/login/"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_token(self, jwt_auth: JWTAuth, request_basic: Request) -> None:
        """Test authenticate raises HTTPException with invalid token."""
        request_basic._cookies = {"user_session": "invalid_token"}

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.authenticate(request_basic)

        assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert exc_info.value.headers is not None
        assert exc_info.value.headers["Location"] == "/pages/auth/login/"

    @pytest.mark.asyncio
    async def test_authenticate_expired_token(
        self, jwt_auth: JWTAuth, user_doc: UserDoc, request_basic: Request
    ) -> None:
        """Test authenticate raises HTTPException with expired token."""
        # Create an expired token
        expired_time = int(time.time()) - 3600
        jwt_data = {"exp": expired_time, "user_id": str(user_doc.id)}
        expired_token = jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

        request_basic._cookies = {"user_session": expired_token}

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.authenticate(request_basic)

        assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert exc_info.value.headers is not None
        assert "Location" in exc_info.value.headers

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, jwt_auth: JWTAuth, request_basic: Request) -> None:
        """Test authenticate raises HTTPException when user doesn't exist."""
        # Create token with non-existent user_id
        fake_id = PydanticObjectId()
        jwt_data = {"exp": int(time.time()) + 3600, "user_id": str(fake_id)}
        token = jwt.encode(payload=jwt_data, key=AppSettings.CRYPTO_SECRET, algorithm="HS256")

        request_basic._cookies = {"user_session": token}

        with pytest.raises(HTTPException) as exc_info:
            await jwt_auth.authenticate(request_basic)

        assert exc_info.value.status_code == status.HTTP_307_TEMPORARY_REDIRECT
        assert exc_info.value.headers is not None
        assert "Location" in exc_info.value.headers


class ExampleBasicAuth(BasicAuth[UserDoc]):
    """BasicAuth class for testing."""


basic_auth = ExampleBasicAuth(user_model=UserDoc)


class TestBasicAuth:
    """Test cases for BasicAuth class."""

    @pytest_asyncio.fixture
    async def user_doc(self) -> typing.AsyncGenerator[UserDoc, None]:
        """Create a test user document."""
        user = await UserDoc(
            username="basicuser",
            email="basic@example.com",
            auth_key="test_auth_key_12345",
        ).create()
        user.set_password("basicpassword123")
        await user.save()
        yield user
        await user.delete()

    @pytest_asyncio.fixture
    async def user_doc_no_auth_key(self) -> typing.AsyncGenerator[UserDoc, None]:
        """Create a test user document without auth_key."""
        user = await UserDoc(
            username="basicuser2",
            email="basic2@example.com",
        ).create()
        user.set_password("basicpassword456")
        await user.save()
        yield user
        await user.delete()

    @pytest.fixture
    def basic_auth_no_model(self) -> ExampleBasicAuth:
        """Create a BasicAuth instance without user model."""
        return ExampleBasicAuth(user_model=None)

    @pytest.fixture
    def basic_auth_no_key_attr(self) -> ExampleBasicAuth:
        """Create a BasicAuth instance that uses ID instead of auth_key."""

        class BasicAuthNoKey(ExampleBasicAuth):
            """BasicAuth subclass that doesn't use auth_key."""

            def get_auth_key_attribute(self) -> str | None:
                """Override to return None, forcing ID-based lookup."""
                return None

        return BasicAuthNoKey(user_model=UserDoc)

    def create_request_with_headers(self, request_basic: Request, authorization: str | None = None) -> Request:
        """Create a Request object with custom headers."""
        headers_auth = {}
        if authorization:
            headers_auth = {"headers": [(b"authorization", authorization.encode())]}
        return Request(scope=request_basic.scope | headers_auth)  # type: ignore

    @pytest.mark.asyncio
    async def test_retrieve_user_by_auth_key(self, user_doc: UserDoc) -> None:
        """Test retrieve_user successfully retrieves user by auth_key."""
        assert user_doc.auth_key is not None
        retrieved_user: UserDoc = await basic_auth.retrieve_user(user_doc.auth_key)
        assert retrieved_user.id == user_doc.id

    @pytest.mark.asyncio
    async def test_retrieve_user_nonexistent(self) -> None:
        """Test retrieve_user raises error for non-existent user."""
        fake_id = PydanticObjectId()

        with pytest.raises((Object404Error, AttributeError)):
            await basic_auth.retrieve_user(str(fake_id))

    @pytest.mark.asyncio
    async def test_retrieve_user_no_model(self, basic_auth_no_model: ExampleBasicAuth) -> None:
        """Test retrieve_user raises NotImplementedError when no model is set."""
        with pytest.raises(NotImplementedError):
            await basic_auth_no_model.retrieve_user("test_key")

    @pytest.mark.asyncio
    async def test_authenticate_success_with_auth_key(self, request_basic: Request, user_doc: UserDoc) -> None:
        """Test authenticate successfully authenticates user with auth_key."""
        # Create basic auth header using auth_key
        assert user_doc.auth_key is not None
        credentials = base64.b64encode(f"{user_doc.auth_key}:".encode()).decode("ascii")
        request_auth = self.create_request_with_headers(request_basic, authorization=f"Basic {credentials}")
        user: UserDoc = await basic_auth.authenticate(request_auth)
        assert user.username == user_doc.username

    @pytest.mark.asyncio
    async def test_authenticate_success_with_id(
        self, request_basic: Request, basic_auth_no_key_attr: ExampleBasicAuth, user_doc_no_auth_key: UserDoc
    ) -> None:
        """Test authenticate successfully authenticates user with ID when auth_key attribute is not used."""
        # Create basic auth header using ID
        credentials = base64.b64encode(f"{user_doc_no_auth_key.id}:password".encode()).decode("ascii")
        mock_request = self.create_request_with_headers(request_basic, authorization=f"Basic {credentials}")

        user: UserDoc = await basic_auth_no_key_attr.authenticate(mock_request)
        assert user.username == user_doc_no_auth_key.username

    @pytest.mark.asyncio
    async def test_authenticate_success_with_username_only(self, request_basic: Request, user_doc: UserDoc) -> None:
        """Test authenticate with username only (no colon in credentials)."""
        # Create basic auth header with just auth_key (no password)
        assert user_doc.auth_key is not None
        credentials = base64.b64encode(f"{user_doc.auth_key}".encode()).decode("ascii")
        mock_request = self.create_request_with_headers(request_basic, authorization=f"Basic {credentials}")

        user: UserDoc = await basic_auth.authenticate(mock_request)
        assert user.username == user_doc.username

    @pytest.mark.asyncio
    async def test_authenticate_success_with_password_only(self, request_basic: Request, user_doc: UserDoc) -> None:
        """Test authenticate with password only (username empty)."""
        # Create basic auth header with empty username
        assert user_doc.auth_key is not None
        credentials = base64.b64encode(f":{user_doc.auth_key}".encode()).decode("ascii")
        mock_request = self.create_request_with_headers(request_basic, authorization=f"Basic {credentials}")

        user: UserDoc = await basic_auth.authenticate(mock_request)
        assert user.username == user_doc.username

    @pytest.mark.asyncio
    async def test_authenticate_missing_header(self, request_basic: Request) -> None:
        """Test authenticate raises HTTPException when Authorization header is missing."""
        mock_request = self.create_request_with_headers(request_basic, authorization=None)

        with pytest.raises(HTTPException) as exc_info:
            await basic_auth.authenticate(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Authentication required"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_scheme(self, request_basic: Request) -> None:
        """Test authenticate raises HTTPException with non-Basic auth scheme."""
        mock_request = self.create_request_with_headers(request_basic, authorization="Bearer some_token")

        with pytest.raises(HTTPException) as exc_info:
            await basic_auth.authenticate(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Only basic authorization is supported"

    @pytest.mark.asyncio
    async def test_authenticate_invalid_base64(self, request_basic: Request) -> None:
        """Test authenticate raises HTTPException with invalid base64 credentials."""
        mock_request = self.create_request_with_headers(request_basic, authorization="Basic not_valid_base64!!!")

        with pytest.raises(HTTPException) as exc_info:
            await basic_auth.authenticate(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Error while decoding basic auth credentials"

    @pytest.mark.asyncio
    async def test_authenticate_nonexistent_user(self, request_basic: Request) -> None:
        """Test authenticate raises HTTPException when user doesn't exist."""
        # Use a fake auth key that doesn't exist
        credentials = base64.b64encode(b"fake_auth_key_9999:password")
        mock_request = self.create_request_with_headers(
            request_basic, authorization=f"Basic {credentials.decode('ascii')}"
        )

        with pytest.raises(HTTPException) as exc_info:
            await basic_auth.authenticate(mock_request)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid basic auth credentials"
