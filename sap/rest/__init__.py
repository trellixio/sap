"""
Rest.

This package regroups all common helpers to work with a RESTful API.
"""

from .client import RestClient, RestData, BeansClient

__all__ = [
    "RestClient",
    "RestData",
    "BeansClient",
]
