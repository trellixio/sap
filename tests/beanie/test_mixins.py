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
    async def test_set_password(self, user: UserDoc) -> None:
        """Test set_password hashes and stores password correctly."""
        # Initially hashed_password should be None
        assert not user.hashed_password

        # Set a password
        user.set_password("secure_password_123")

        # Check that hashed_password is now set and is not the plain password
        assert user.hashed_password and user.hashed_password.startswith("$2b$")  # type: ignore

    @pytest.mark.asyncio
    async def test_verify_password_correct(self, user: UserDoc) -> None:
        """Test verify_password returns True for correct password."""
        password = "my_secure_password"
        user.set_password(password)

        # Verify with correct password
        assert user.verify_password(password) is True

    @pytest.mark.asyncio
    async def test_verify_password_incorrect(self, user: UserDoc) -> None:
        """Test verify_password returns False for incorrect password."""
        user.set_password("correct_password")

        # Verify with incorrect password
        assert user.verify_password("wrong_password") is False
        assert user.verify_password("") is False
        assert user.verify_password("correct_passwor") is False

    @pytest.mark.asyncio
    async def test_set_password_changes_hash(self, user: UserDoc) -> None:
        """Test that setting password multiple times changes the hash."""
        user.set_password("password1")
        first_hash = user.hashed_password

        user.set_password("password2")
        second_hash = user.hashed_password

        # Hashes should be different
        assert first_hash != second_hash

        # Old password should not work
        assert user.verify_password("password1") is False

        # New password should work
        assert user.verify_password("password2") is True

    @pytest.mark.asyncio
    async def test_password_persistence(self) -> None:
        """Test that password hash persists after saving to database."""
        # Create user with password
        user = await UserDoc(username="persisttest", email="persist@example.com").create()
        user.set_password("test_password_123")
        await user.save()

        # Retrieve user from database
        assert user.id is not None
        retrieved_user = await UserDoc.get(user.id)
        assert retrieved_user is not None

        # Password should still verify
        assert retrieved_user.verify_password("test_password_123") is True
        assert retrieved_user.verify_password("wrong") is False

        # Clean up
        await user.delete()

    @pytest.mark.asyncio
    async def test_same_password_different_hashes(self, user: UserDoc) -> None:
        """Test that same password generates different hashes (due to salt)."""
        password = "same_password"

        user.set_password(password)
        first_hash = user.hashed_password

        user.set_password(password)
        second_hash = user.hashed_password

        # Hashes should be different due to different salt
        assert first_hash != second_hash

        # But both should verify the same password
        user.hashed_password = first_hash
        assert user.verify_password(password) is True

        user.hashed_password = second_hash
        assert user.verify_password(password) is True

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
