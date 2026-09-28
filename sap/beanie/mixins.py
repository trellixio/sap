"""Mixin for User models."""

import bcrypt
import passlib.context

import pydantic

_bcrypt_hashpw = bcrypt.hashpw


def _hashpw(password: bytes, salt: bytes) -> bytes:
    """Hash a password, keeping bcrypt's historical 72-byte truncation."""
    # bcrypt 5 raises above 72 bytes. passlib 1.7 still probes that limit.
    return _bcrypt_hashpw(password[:72], salt)


bcrypt.hashpw = _hashpw

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
            password: The password to hash. bcrypt uses the first 72 bytes.
        """
        self.hashed_password = crypt_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify if a password matches hash in the database."""
        return crypt_context.verify(password, self.hashed_password)
