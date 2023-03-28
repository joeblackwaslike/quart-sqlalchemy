from __future__ import annotations

import typing as t
from datetime import datetime
from datetime import timezone

import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.engine.interfaces
import sqlalchemy.sql.type_api
import sqlalchemy.types
from pydantic import BaseModel
from pydantic import parse_obj_as


sa = sqlalchemy


class PydanticType(sa.types.TypeDecorator):
    """Pydantic type.

    SAVING:
    - Uses SQLAlchemy JSON type under the hood.
    - Accepts the pydantic model and converts it to a dict on save.
    - SQLAlchemy engine JSON-encodes the dict to a string.

    RETRIEVING:
    - Pulls the string from the database.
    - SQLAlchemy engine JSON-decodes the string to a dict.
    - Uses the dict to create a pydantic model.
    """

    impl = sa.types.JSON
    cache_ok = False

    pydantic_type: BaseModel

    def __init__(self, pydantic_type: BaseModel):
        super().__init__()
        self.pydantic_type = pydantic_type

    def load_dialect_impl(
        self,
        dialect: sa.engine.interfaces.Dialect,
    ) -> sa.sql.type_api.TypeEngine[t.Any]:
        # Use JSONB for PostgreSQL and JSON for other databases.
        if dialect.name == "postgresql":
            return dialect.type_descriptor(sa.dialects.postgresql.JSONB())
        else:
            return dialect.type_descriptor(sa.JSON())

    def process_bind_param(
        self,
        value: t.Optional[BaseModel],
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Any:
        """Receive a bound parameter value to be converted/serialized."""
        return value.dict() if value else None
        # If you use FasAPI, you can replace the line above with their jsonable_encoder().
        # E.g.,
        # from fastapi.encoders import jsonable_encoder
        # return jsonable_encoder(value) if value else None

    def process_result_value(
        self,
        value: t.Optional[str],
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Optional[BaseModel]:
        """Receive a result-row column value to be converted/deserialized."""
        return parse_obj_as(self.pydantic_type, value) if value else None


class TZDateTime(sa.types.TypeDecorator):
    impl = sa.types.DateTime
    cache_ok = True

    def process_bind_param(
        self,
        value: t.Optional[datetime],
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Any:
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def process_result_value(
        self,
        value: t.Optional[str],
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Optional[datetime]:
        if value is not None:
            value = value.replace(tzinfo=timezone.utc)
        return value
