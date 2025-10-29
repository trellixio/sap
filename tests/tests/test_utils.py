"""Tests for sap/tests/utils.py."""

from sap.tests.utils import generate_random_email, generate_random_string, stringify_request_key


def test_generate_random_string() -> None:
    """Test generate_random_string creates string of correct length."""
    result = generate_random_string(10)
    assert len(result) == 10
    assert result.isalnum()

    result2 = generate_random_string(20)
    assert len(result2) == 20
    assert result != result2


def test_generate_random_email() -> None:
    """Test generate_random_email creates valid email format."""
    email = generate_random_email()
    assert "@yopmail.net" in email
    assert email.startswith("trellis-test.")
    assert len(email.split("@")[0]) == 9 + len("trellis-test.")


def test_generate_random_email_custom_domain() -> None:
    """Test generate_random_email with custom domain."""
    email = generate_random_email(domain="example.com")
    assert "@example.com" in email
    assert email.startswith("trellis-test.")


def test_generate_random_email_custom_length() -> None:
    """Test generate_random_email with custom length."""
    email = generate_random_email(length=15)
    local_part = email.split("@")[0]
    assert len(local_part) == 15 + len("trellis-test.")


def test_stringify_request_key_none() -> None:
    """Test stringify_request_key with None."""
    result = stringify_request_key(None)
    assert result == "None"


def test_stringify_request_key_simple_dict() -> None:
    """Test stringify_request_key with simple dictionary."""
    obj = {"key1": "value1", "key2": "value2"}
    result = stringify_request_key(obj)
    assert "key1_value1" in result
    assert "key2_value2" in result
    assert "-" in result


def test_stringify_request_key_nested_dict() -> None:
    """Test stringify_request_key with nested dictionary."""
    obj = {"key1": "value1", "nested": {"inner_key": "inner_value"}}
    result = stringify_request_key(obj)
    assert "key1_value1" in result
    assert "nested_" in result
    assert "inner_key_inner_value" in result


def test_stringify_request_key_with_numbers() -> None:
    """Test stringify_request_key with numeric values."""
    obj = {"count": 42, "price": 99.99}
    result = stringify_request_key(obj)
    assert "count_42" in result
    assert "price_99.99" in result
