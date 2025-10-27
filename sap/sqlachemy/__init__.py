"""SQLAlchemy."""

from typing import TypeVar, Union

import pydantic

try:
    from sqlalchemy.orm import DeclarativeBase
except ImportError:
    from pydantic import BaseModel as DeclarativeBase  # type: ignore


AlchemyModelT = TypeVar("AlchemyModelT", bound=DeclarativeBase)
AlchemyOrPydanticModelT = TypeVar("AlchemyOrPydanticModelT", bound=Union[pydantic.BaseModel, DeclarativeBase])
