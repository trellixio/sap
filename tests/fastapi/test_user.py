"""Tests for fastapi/user.py."""

import typing

import pytest
import pytest_asyncio

from tests.samples import UserDoc


@pytest_asyncio.fixture
async def user_admin_doc() -> typing.AsyncGenerator[UserDoc, None]:
    """Create a test user document."""
    user = await UserDoc(role="admin", username="testuser", email="test@example.com").create()
    yield user
    await user.delete()


@pytest_asyncio.fixture
async def user_viewer_doc() -> typing.AsyncGenerator[UserDoc, None]:
    """Create a test user document."""
    user = await UserDoc(role="viewer", username="testuser", email="test@example.com").create()
    yield user
    await user.delete()


@pytest.mark.asyncio
async def test_user_mixin(user_admin_doc: UserDoc, user_viewer_doc: UserDoc) -> None:
    """Test UserMixin class, including get_role, has_perm, and has_perms methods."""
    assert user_admin_doc.get_role() == "admin"
    assert user_admin_doc.has_perm("*") is True
    assert user_admin_doc.has_perm("admin") is True
    assert user_admin_doc.has_perm("Admin") is False
    assert user_admin_doc.has_perm("viewer") is False
    assert user_admin_doc.has_perm("") is False
    assert user_admin_doc.has_perms(["admin", "viewer"]) is True
    assert user_admin_doc.has_perms(["viewer", "editor"]) is False

    assert user_viewer_doc.get_role() == "viewer"
    assert user_viewer_doc.has_perm("admin") is False
    assert user_viewer_doc.has_perm("viewer") is True
