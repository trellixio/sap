"""Mixins to implement a User model."""


class UserMixin:
    """Represent a user of the platform."""

    role: str

    def get_role(self) -> str:
        """Return the role of the user."""
        return self.role

    def has_perm(self, perm: str) -> bool:
        """Check if the user has access to a specific role permission."""
        if perm == "*":
            return True
        return self.role == perm

    def has_perms(self, perms: list[str]) -> bool:
        """Check if the user has access to any of the provided permissions."""
        return any(self.has_perm(perm) for perm in perms)

    async def get_auth_key(self) -> str:
        """Return an auth_key allowing the user to authenticate. Useful for testing."""
        raise NotImplementedError
