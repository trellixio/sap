"""
Utils.

Re-usable methods and functions for all test cases.
"""

import random
import string


def get_random_email(domain: str = "yopmail.net", length: int = 9) -> str:
    """Get a random email to be using in test cases."""
    random_string = "".join(random.choice(string.ascii_lowercase) for _ in range(length))
    return "trellis-test." + random_string + "@" + domain
