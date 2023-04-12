from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.sql
from sqlalchemy.orm.interfaces import ORMOption

from quart_sqlalchemy.types import ColumnExpr
from quart_sqlalchemy.types import DMLTable
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import Selectable


sa = sqlalchemy


class StatementBuilder(t.Generic[EntityT]):
    model: t.Optional[t.Type[EntityT]]

    def __init__(self, model: t.Optional[t.Type[EntityT]] = None):
        self.model = model

    def select(
        self,
        selectables: t.Sequence[Selectable] = (),
        conditions: t.Sequence[ColumnExpr] = (),
        group_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        order_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        offset: t.Optional[int] = None,
        limit: t.Optional[int] = None,
        distinct: bool = False,
        for_update: bool = False,
    ) -> sa.Select:
        statement = sa.select(*selectables or self.model).where(*conditions)

        if for_update:
            statement = statement.with_for_update()
        if offset:
            statement = statement.offset(offset)
        if limit:
            statement = statement.limit(limit)
        if group_by:
            statement = statement.group_by(*group_by)
        if order_by:
            statement = statement.order_by(*order_by)

        for option in options:
            for context in option.context:
                for strategy in context.strategy:
                    if "joined" in strategy:
                        distinct = True

            statement = statement.options(option)

        if distinct:
            statement = statement.distinct()

        if execution_options:
            statement = statement.execution_options(**execution_options)

        return statement

    def insert(
        self,
        target: t.Optional[DMLTable] = None,
        values: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Insert:
        return sa.insert(target or self.model).values(**values or {})

    def bulk_insert(
        self,
        target: t.Optional[DMLTable] = None,
        values: t.Sequence[t.Dict[str, t.Any]] = (),
    ) -> sa.Insert:
        return sa.insert(target or self.model).values(*values)

    def bulk_update(
        self,
        target: t.Optional[DMLTable] = None,
        conditions: t.Sequence[ColumnExpr] = (),
        values: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Update:
        return sa.update(target or self.model).where(*conditions).values(**values or {})

    def bulk_delete(
        self,
        target: t.Optional[DMLTable] = None,
        conditions: t.Sequence[ColumnExpr] = (),
    ) -> sa.Delete:
        return sa.delete(target or self.model).where(*conditions)
