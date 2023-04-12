from __future__ import annotations

import operator
import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.sql
from builder import StatementBuilder
from meta import TableMetadataMixin

from base import AbstractBulkRepository
from base import AbstractRepository
from quart_sqlalchemy.types import ColumnExpr
from quart_sqlalchemy.types import EntityIdT
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import Operator
from quart_sqlalchemy.types import ORMOption
from quart_sqlalchemy.types import Selectable
from quart_sqlalchemy.types import SessionT


sa = sqlalchemy


class SQLAlchemyRepository(
    TableMetadataMixin,
    AbstractRepository[EntityT, EntityIdT, SessionT],
    t.Generic[EntityT, EntityIdT, SessionT],
):
    """A repository that uses SQLAlchemy to persist data.

    The biggest change with this repository is that for methods returning multiple results, we
    return the sa.ScalarResult so that the caller has maximum flexibility in how it's consumed.

    As a result, when calling a method such as get_by, you then need to decide how to fetch the
    result.

    Methods of fetching results:
      - .all() to return a list of results
      - .first() to return the first result
      - .one() to return the first result or raise an exception if there are no results
      - .one_or_none() to return the first result or None if there are no results
      - .partitions(n) to return a results as a list of n-sized sublists

    Additionally, there are methods for transforming the results prior to fetching.

    Methods of transforming results:
      - .unique() to apply unique filtering to the result

    """

    session: sa.orm.Session
    builder: StatementBuilder

    def __init__(self, model: sa.orm.Session, **kwargs):
        super().__init__(**kwargs)
        self.session = session
        self.builder = StatementBuilder(None)

    def insert(self, values: t.Dict[str, t.Any]) -> EntityT:
        """Insert a new model into the database."""
        new = self.model(**values)
        self.session.add(new)
        self.session.flush()
        self.session.refresh(new)
        return new

    def update(self, id_: EntityIdT, values: t.Dict[str, t.Any]) -> EntityT:
        """Update existing model with new values."""
        obj = self.session.get(self.model, id_)
        if obj is None:
            raise ValueError(f"Object with id {id_} not found")
        for field, value in values.items():
            if getattr(obj, field) != value:
                setattr(obj, field, value)
        self.session.flush()
        self.session.refresh(obj)
        return obj

    def merge(
        self, id_: EntityIdT, values: t.Dict[str, t.Any], for_update: bool = False
    ) -> EntityT:
        """Merge model in session/db having id_ with values."""
        self.session.get(self.model, id_)
        values.update(id=id_)
        merged = self.session.merge(self.model(**values))
        self.session.flush()
        self.session.refresh(merged, with_for_update=for_update)  # type: ignore
        return merged

    def get(
        self,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> t.Optional[EntityT]:
        """Get object identified by id_ from the database.

        Note: It's a common misconception that session.get(Model, id) is akin to a shortcut for
        a select(Model).where(Model.id == id) like statement.  However this is not the case.

        Session.get is actually used for looking an object up in the sessions identity map.  When
        present it will be returned directly, when not, a database lookup will be performed.

        For use cases where this is what you actually want, you can still access the original get
        method on self.session.  For most uses cases, this behavior can introduce non-determinism
        and because of that this method performs lookup using a select statement.  Additionally,
        to satisfy the expected interface's return type: Optional[EntityT], one_or_none is called
        on the result before returning.
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(self.model).where(self.model.id == id_).limit(1)  # type: ignore

        for option in options:
            statement = statement.options(option)

        if for_update:
            statement = statement.with_for_update()

        return self.session.scalars(statement, execution_options=execution_options).one_or_none()

    def get_by_field(
        self,
        field: t.Union[ColumnExpr, str],
        value: t.Any,
        op: Operator = operator.eq,
        order_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        offset: t.Optional[int] = None,
        limit: t.Optional[int] = None,
        distinct: bool = False,
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> sa.ScalarResult[EntityT]:
        """Select models where field is equal to value."""
        selectables = (self.model,)  # type: ignore

        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        if isinstance(field, str):
            field = getattr(self.model, field)

        conditions = [t.cast(ColumnExpr, op(field, value))]

        statement = self.builder.complex_select(
            selectables,
            conditions=conditions,
            order_by=order_by,
            options=options,
            execution_options=execution_options,
            offset=offset,
            limit=limit,
            distinct=distinct,
            for_update=for_update,
        )

        return self.session.scalars(statement)

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
        include_inactive: bool = False,
        yield_by_chunk: t.Optional[int] = None,
    ) -> t.Union[sa.ScalarResult[EntityT], t.Iterator[t.Sequence[EntityT]]]:
        """Select from the database.

        Note: yield_by_chunk is not compatible with the subquery and joined loader strategies, use selectinload for eager loading.
        """
        selectables = selectables or (self.model,)  # type: ignore

        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)
        if yield_by_chunk:
            execution_options.setdefault("yield_per", yield_by_chunk)

        statement = self.builder.complex_select(
            selectables,
            conditions=conditions,
            group_by=group_by,
            order_by=order_by,
            options=options,
            execution_options=execution_options,
            offset=offset,
            limit=limit,
            distinct=distinct,
            for_update=for_update,
        )

        results = self.session.scalars(statement)
        if yield_by_chunk:
            results = results.partitions()
        return results

    def delete(self, id_: EntityIdT) -> None:
        if self.has_soft_delete:
            raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        entity = self.get(id_)
        if not entity:
            raise RuntimeError(f"Entity with id {id_} not found.")

        self.session.delete(entity)
        self.session.flush()

    def deactivate(self, id_: EntityIdT) -> EntityT:
        if not self.has_soft_delete:
            raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        return self.update(id_, dict(is_active=False))

    def reactivate(self, id_: EntityIdT) -> EntityT:
        if not self.has_soft_delete:
            raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        return self.update(id_, dict(is_active=False))

    def exists(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> bool:
        """Return whether an object matching conditions exists.

        Note: This performs better than simply trying to select an object since there is no
        overhead in sending the selected object and deserializing it.
        """
        selectable = sa.sql.literal(True)

        execution_options = {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(selectable).where(*conditions)  # type: ignore

        if for_update:
            statement = statement.with_for_update()

        result = self.session.execute(statement, execution_options=execution_options).scalar()

        return bool(result)

    # def get_or_insert(
    #     self,
    #     values: t.Dict[str, t.Any],
    #     unique_columns: t.Sequence[ColumnExpr] = (),
    #     execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    #     include_inactive: bool = False,
    # ) -> EntityT:
    #     """Add `data` to the collection."""
    #     selectable = self.model

    #     execution_options = {}
    #     if include_inactive:
    #         execution_options.setdefault("include_inactive", include_inactive)

    #     lookup_conditions = {field: val for field, val in values.items() if field in unique_columns}
    #     lookup_statement = sa.select(selectable).filter_by(*lookup_conditions)
    #     try:
    #         return self.session.scalars(lookup_statement, execution_options=execution_options).one()
    #     except sa.orm.exc.NoResultFound:
    #         obj = self.model(**values)
    #         self.session.add(obj)
    #         try:
    #             with self.session.begin_nested():
    #                 self.session.flush()
    #         except sa.exc.IntegrityError:
    #             self.session.rollback()
    #             try:
    #                 self.session.scalars(sa.select(selectable).filter_by(*lookup_conditions)).one()
    #             except sa.orm.exc.NoResultFound:
    #                 raise
    #             else:
    #                 return obj
    #         else:
    #             return obj


class SQLAlchemyBulkRepository(AbstractBulkRepository, t.Generic[SessionT, EntityT, EntityIdT]):
    def __init__(self, session: SessionT, **kwargs: t.Any):
        super().__init__(**kwargs)
        self.builder = StatementBuilder(self.model)
        self.session = session

    def bulk_insert(
        self,
        values: t.Sequence[t.Dict[str, t.Any]] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_insert(self.model, values)
        return self.session.execute(statement, execution_options=execution_options or {})

    def bulk_update(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        values: t.Optional[t.Dict[str, t.Any]] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_update(self.model, conditions, values)
        return self.session.execute(statement, execution_options=execution_options or {})

    def bulk_delete(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_delete(self.model, conditions)
        return self.session.execute(statement, execution_options=execution_options or {})
