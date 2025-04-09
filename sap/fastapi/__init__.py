"""
FastAPI.

This package regroups all common helpers exclusively for FastAPI.
Learn more about FastAPI: https://github.com/tiangolo/fastapi
"""

from sap.exceptions import Object404Error, Validation422Error

from .forms import FormValidation, validate_form
from .serializers import CustomJSONEncoder, ObjectSerializer, WriteObjectSerializer
from .utils import Flash, FlashLevel, pydantic_format_errors

__all__ = [
    "Flash",
    "FlashLevel",
    "pydantic_format_errors",
    # Serializers
    "ObjectSerializer",
    "WriteObjectSerializer",
    "CustomJSONEncoder",
    # Exceptions
    "Validation422Error",
    "Object404Error",
    # Forms
    "validate_form",
    "FormValidation",
]
