import typing as t
from datetime import UTC, datetime

import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.engine.interfaces
import sqlalchemy.sql.type_api
import sqlalchemy.types
from pydantic import BaseModel, TypeAdapter

sa = sqlalchemy


class PydanticType(sa.types.TypeDecorator[t.Any]):
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
        return dialect.type_descriptor(sa.JSON())

    def process_bind_param(
        self,
        value: BaseModel | None,
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Any:
        """Receive a bound parameter value to be converted/serialized."""
        return value.model_dump() if value else None
        # If you use FasAPI, you can replace the line above with their jsonable_encoder().
        # E.g.,
        # from fastapi.encoders import jsonable_encoder
        # return jsonable_encoder(value) if value else None

    def process_result_value(
        self,
        value: str | None,
        dialect: sa.engine.interfaces.Dialect,
    ) -> BaseModel | None:
        """Receive a result-row column value to be converted/deserialized."""
        return TypeAdapter(self.pydantic_type).validate_python(value) if value else None


class TZDateTime(sa.types.TypeDecorator[datetime]):
    impl = sa.types.DateTime(timezone=True)
    cache_ok = True

    @property
    def python_type(self) -> type[datetime]:
        return datetime

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: sa.engine.interfaces.Dialect,
    ) -> t.Any:
        if value is not None:
            if not value.tzinfo:
                raise TypeError("tzinfo is required")
            value = value.astimezone(UTC)
        return value

    def process_result_value(
        self,
        value: datetime | None,
        dialect: sa.engine.interfaces.Dialect,
    ) -> datetime | None:
        if value is not None:
            return value.replace(tzinfo=UTC)
        return value
