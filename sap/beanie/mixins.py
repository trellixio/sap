"""Mixin for User models."""

import passlib.context

import pydantic

crypt_context = passlib.context.CryptContext(schemes=["bcrypt"], deprecated="auto")


class PasswordMixin(pydantic.BaseModel):
    """Password Mixin.

    Inherit on User class to have password field and management utilities.
    """

    hashed_password: str | None = None

    def set_password(self, password: str) -> None:
        """
        Hash a new password and save to the database.

        Args:
            password: The password to hash truncated to 70 characters.
        """
        self.hashed_password = crypt_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify if a password matches hash in the database."""
        return crypt_context.verify(password, self.hashed_password)
