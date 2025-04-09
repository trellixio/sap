"""
Helpers for views.

Helpers methods used in app.views.
"""

from dataclasses import dataclass
from typing import Any, Generic, Optional

import pydantic
from fastapi import Request

from sap.exceptions import Validation422Error
from sap.sqlachemy import AlchemyOrPydanticModelT

from .serializers import SerializerT, WSerializerT
from .utils import Flash, FlashLevel, merge_dict_deep, pydantic_format_errors, unflatten_form_data


@dataclass
class FormValidation(Generic[WSerializerT]):
    """Return the result of data validation for a form serializer."""

    data: dict[str, Any]
    errors: dict[str, Any]
    serializer: Optional[WSerializerT]


async def validate_form(
    request: Request,
    serializer_write_class: type[WSerializerT],
    serializer_read_class: Optional[type[SerializerT]] = None,
    instance: Optional[AlchemyOrPydanticModelT] = None,
) -> FormValidation[WSerializerT]:
    """Check that a submitted form pass validation."""
    form_data: dict[str, Any] = {}

    if serializer_read_class and instance:
        # Means this is an update. So we first populate existing data
        serializer_read: SerializerT = serializer_read_class.read(instance=instance)
        form_data = serializer_read.model_dump()

    form_data_received = await request.form()
    form_data = merge_dict_deep(form_data, unflatten_form_data(form_data_received))
    form_errors: dict[str, Any] = {}

    async def run_validation() -> WSerializerT:
        """Run serializer validation."""
        serializer_: WSerializerT = serializer_write_class(**form_data)
        serializer_.instance = instance
        await serializer_.run_async_validators(request=request)
        return serializer_

    serializer_write: Optional[WSerializerT] = None

    try:
        serializer_write = await run_validation()
    except pydantic.ValidationError as err:
        form_errors = pydantic_format_errors(err.errors())
        msg = "Please review submitted form."
        form_errors["__root__"] = {"msg": msg}
        Flash.add_message(request, msg, level=FlashLevel.ERROR)
    except (AssertionError, Validation422Error) as err:
        form_errors["__root__"] = {"msg": str(err)}
        Flash.add_message(request, str(err), level=FlashLevel.ERROR)

    return FormValidation(serializer=serializer_write, data=form_data, errors=form_errors)
