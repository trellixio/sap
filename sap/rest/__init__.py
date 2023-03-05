"""
Rest.

This package regroups all common helpers to work with a RESTful API.
"""

from .client import BeansClient, RestClient, RestData

__all__ = [
    "RestClient",
    "RestData",
    "BeansClient",
]
