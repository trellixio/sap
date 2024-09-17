# pylint: disable=useless-import-alias

"""
Typing.

Provide helper for common typing syntax.
"""

try:
    from types import UnionType as UnionType
except ImportError:
    from typing import Union as UnionType  # type: ignore
