from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.sql.schema


sa = sqlalchemy


class _Table(sa.Table):
    @t.overload
    def __init__(
        self,
        name: str,
        *args: sa.sql.schema.SchemaItem,
        bind_key: str | None = None,
        **kwargs,
    ) -> None:
        ...

    @t.overload
    def __init__(
        self,
        name: str,
        metadata: sa.MetaData,
        *args: sa.sql.schema.SchemaItem,
        **kwargs,
    ) -> None:
        ...

    @t.overload
    def __init__(self, name: str, *args: sa.sql.schema.SchemaItem, **kwargs) -> None:
        ...

    def __init__(self, name: str, *args: sa.sql.schema.SchemaItem, **kwargs) -> None:
        super().__init__(name, *args, **kwargs)  # type: ignore[arg-type]
