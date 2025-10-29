# pylint: disable=no-self-use
"""Tests for PasswordMixin class."""

import pytest
import pytest_asyncio

from tests.samples import UserDoc


class TestPasswordMixin:
    """Test cases for PasswordMixin class."""

    @pytest_asyncio.fixture
    async def user(self) -> UserDoc:
        """Create a test user."""
        return await UserDoc(username="testuser", email="test@example.com").create()

    @pytest.mark.asyncio
    async def test_verify_password(self, user: UserDoc) -> None:
        """Test verify_password returns True for correct password."""
        password = "my_secure_password"
        user.set_password(password)

        # Test verify_password returns False for incorrect password.
        assert user.hashed_password and user.hashed_password.startswith("$2b$")  # type: ignore

        # Test verify_password returns True for correct password.
        assert user.verify_password(password) is True

        # Test verify_password returns False for incorrect password.
        assert user.verify_password("wrong_password") is False

        # Test that setting password multiple times changes the hash.
        first_hash = user.hashed_password
        user.set_password(password)
        second_hash = user.hashed_password
        assert first_hash != second_hash

        user.hashed_password = first_hash
        assert user.verify_password(password) is True

        user.hashed_password = second_hash
        assert user.verify_password(password) is True

        # Test that password hash persists after saving to database.
        await user.save()
        await user.refresh_from_db()
        assert user.verify_password(password) is True

        # New password should work
        user.set_password("password2")
        assert user.verify_password(password) is False
        assert user.verify_password("password2") is True

    @pytest.mark.asyncio
    async def test_empty_password(self, user: UserDoc) -> None:
        """Test setting and verifying empty password."""
        user.set_password("")
        assert user.hashed_password is not None
        assert user.verify_password("") is True

    @pytest.mark.asyncio
    async def test_special_characters_in_password(self, user: UserDoc) -> None:
        """Test password with special characters."""
        special_password = "p@ssw0rd!#$%^&*()_+-=[]{}|;:',.<>?/~`"
        user.set_password(special_password)
        assert user.verify_password(special_password) is True

    @pytest.mark.asyncio
    async def test_unicode_password(self, user: UserDoc) -> None:
        """Test password with unicode characters."""
        unicode_password = "пароль密码🔒"
        user.set_password(unicode_password)
        assert user.verify_password(unicode_password) is True

    @pytest.mark.asyncio
    async def test_long_password(self, user: UserDoc) -> None:
        """Test very long password."""
        long_password = "a" * 73  # 72 characters is the maximum length supported by bcrypt
        user.set_password(long_password)
        assert user.verify_password(long_password) is True
        assert user.verify_password("a" * 999) is True
