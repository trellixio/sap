"""
Utils.

Re-usable methods and functions for all test cases.
"""

import random
import string


def generate_random_string(length: int) -> str:
    """Generate a random string of a given length"""
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def generate_random_email(domain: str = "yopmail.net", length: int = 9) -> str:
    """Get a random email to be using in test cases."""
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(length))
    return "trellis-test." + random_string + "@" + domain
