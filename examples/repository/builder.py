import typing as t

import sqlalchemy
from sqlalchemy.orm.interfaces import ORMOption

from quart_sqlalchemy.types import ColumnExpr, DMLTable, EntityT, Selectable

sa = sqlalchemy


class StatementBuilder(t.Generic[EntityT]):
    model: type[EntityT]

    def __init__(self, model: type[EntityT]):
        self.model = model

    def complex_select(
        self,
        selectables: t.Sequence[Selectable] = (),
        conditions: t.Sequence[ColumnExpr] = (),
        group_by: t.Sequence[ColumnExpr | str] = (),
        order_by: t.Sequence[ColumnExpr | str] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: dict[str, t.Any] | None = None,
        offset: int | None = None,
        limit: int | None = None,
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
        target: DMLTable | None = None,
        values: dict[str, t.Any] | None = None,
    ) -> sa.Insert:
        return sa.insert(target or self.model).values(**values or {})

    def bulk_insert(
        self,
        target: DMLTable | None = None,
        values: t.Sequence[dict[str, t.Any]] = (),
    ) -> sa.Insert:
        return sa.insert(target or self.model).values(*values)

    def bulk_update(
        self,
        target: DMLTable | None = None,
        conditions: t.Sequence[ColumnExpr] = (),
        values: dict[str, t.Any] | None = None,
    ) -> sa.Update:
        return sa.update(target or self.model).where(*conditions).values(**values or {})

    def bulk_delete(
        self,
        target: DMLTable | None = None,
        conditions: t.Sequence[ColumnExpr] = (),
    ) -> sa.Delete:
        return sa.delete(target or self.model).where(*conditions)
