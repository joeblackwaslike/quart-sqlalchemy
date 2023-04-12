from __future__ import annotations

import operator
import typing as t
from abc import ABCMeta

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.sql

from quart_sqlalchemy.sim.builder import StatementBuilder
from quart_sqlalchemy.types import ColumnExpr
from quart_sqlalchemy.types import EntityIdT
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import Operator
from quart_sqlalchemy.types import ORMOption
from quart_sqlalchemy.types import Selectable
from quart_sqlalchemy.types import SessionT


sa = sqlalchemy


class AbstractRepository(t.Generic[EntityT, EntityIdT, SessionT], metaclass=ABCMeta):
    """A repository interface."""

    model: t.Type[EntityT]
    identity: t.Type[EntityIdT]

    def __init__(self, model: t.Type[EntityT], identity: t.Type[EntityIdT]):
        self.model = model
        self.identity = identity


class AbstractBulkRepository(t.Generic[EntityT, EntityIdT, SessionT], metaclass=ABCMeta):
    """A repository interface for bulk operations.

    Note: this interface circumvents ORM internals, breaking commonly expected behavior in order
    to gain performance benefits.  Only use this class whenever absolutely necessary.
    """

    model: t.Type[EntityT]
    identity: t.Type[EntityIdT]

    def __init__(self, model: t.Type[EntityT], identity: t.Type[EntityIdT]):
        self.model = model
        self.identity = identity


class SQLAlchemyRepository(
    AbstractRepository[EntityT, EntityIdT, SessionT], t.Generic[EntityT, EntityIdT, SessionT]
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

    builder: StatementBuilder

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.builder = StatementBuilder(self.model)

    def _build_execution_options(
        self,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        include_inactive: bool = False,
        yield_by_chunk: bool = False,
    ):
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)
        if yield_by_chunk:
            execution_options.setdefault("yield_per", yield_by_chunk)
        return execution_options

    def insert(self, session: sa.orm.Session, values: t.Dict[str, t.Any]) -> EntityT:
        """Insert a new model into the database."""
        new = self.model(**values)

        session.add(new)
        session.flush()
        session.refresh(new)

        return new

    def update(
        self, session: sa.orm.Session, id_: EntityIdT, values: t.Dict[str, t.Any]
    ) -> EntityT:
        """Update existing model with new values."""
        obj = session.get(self.model, id_)
        if obj is None:
            raise ValueError(f"Object with id {id_} not found")
        for field, value in values.items():
            if getattr(obj, field) != value:
                setattr(obj, field, value)

        session.flush()
        session.refresh(obj)

        return obj

    def merge(
        self,
        session: sa.orm.Session,
        id_: EntityIdT,
        values: t.Dict[str, t.Any],
        for_update: bool = False,
    ) -> EntityT:
        """Merge model in session/db having id_ with values."""
        session.get(self.model, id_)
        values.update(id=id_)

        merged = session.merge(self.model(**values))
        session.flush()
        session.refresh(merged, with_for_update=for_update)  # type: ignore

        return merged

    def get(
        self,
        session: sa.orm.Session,
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
        method on session.  For most uses cases, this behavior can introduce non-determinism
        and because of that this method performs lookup using a select statement.  Additionally,
        to satisfy the expected interface's return type: Optional[EntityT], one_or_none is called
        on the result before returning.
        """
        selectables = (self.model,)

        execution_options = self._build_execution_options(
            execution_options, include_inactive=include_inactive
        )
        # execution_options = execution_options or {}
        # if include_inactive:
        #     execution_options.setdefault("include_inactive", include_inactive)

        statement = self.builder.select(
            selectables,  # type: ignore
            conditions=[self.model.id == id_],
            options=options,
            limit=1,
            for_update=for_update,
        )

        return session.scalars(statement, execution_options=execution_options).one_or_none()

    def get_by_field(
        self,
        session: sa.orm.Session,
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
        selectables = (self.model,)

        execution_options = self._build_execution_options(
            execution_options, include_inactive=include_inactive
        )
        # execution_options = execution_options or {}
        # if include_inactive:
        #     execution_options.setdefault("include_inactive", include_inactive)

        if isinstance(field, str):
            field = getattr(self.model, field)

        conditions = [t.cast(ColumnExpr, op(field, value))]

        statement = self.builder.select(
            selectables,  # type: ignore
            conditions=conditions,
            order_by=order_by,
            options=options,
            offset=offset,
            limit=limit,
            distinct=distinct,
            for_update=for_update,
        )

        return session.scalars(statement, execution_options=execution_options)

    def select(
        self,
        session: sa.orm.Session,
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

        execution_options = self._build_execution_options(
            execution_options,
            include_inactive=include_inactive,
            yield_by_chunk=yield_by_chunk,
        )
        # execution_options = execution_options or {}
        # if include_inactive:
        #     execution_options.setdefault("include_inactive", include_inactive)
        # if yield_by_chunk:
        #     execution_options.setdefault("yield_per", yield_by_chunk)

        statement = self.builder.select(
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

        results = session.scalars(statement)
        if yield_by_chunk:
            results = results.partitions()
        return results

    def delete(
        self, session: sa.orm.Session, id_: EntityIdT, include_inactive: bool = False
    ) -> None:
        entity = self.get(session, id_, include_inactive=include_inactive)
        if not entity:
            raise RuntimeError(f"Entity with id {id_} not found.")

        session.delete(entity)
        session.flush()

    def deactivate(self, session: sa.orm.Session, id_: EntityIdT) -> EntityT:
        return self.update(session, id_, dict(is_active=False))

    def reactivate(self, session: sa.orm.Session, id_: EntityIdT) -> EntityT:
        return self.update(session, id_, dict(is_active=False))

    def exists(
        self,
        session: sa.orm.Session,
        conditions: t.Sequence[ColumnExpr] = (),
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> bool:
        """Return whether an object matching conditions exists.

        Note: This performs better than simply trying to select an object since there is no
        overhead in sending the selected object and deserializing it.
        """
        selectables = (sa.sql.literal(True),)

        execution_options = self._build_execution_options(None, include_inactive=include_inactive)
        # execution_options = {}
        # if include_inactive:
        #     execution_options.setdefault("include_inactive", include_inactive)

        statement = self.builder.select(
            selectables,
            conditions=conditions,
            limit=1,
            for_update=for_update,
        )

        result = session.execute(statement, execution_options=execution_options).scalar()

        return bool(result)


class SQLAlchemyBulkRepository(
    AbstractBulkRepository[EntityT, EntityIdT, SessionT], t.Generic[EntityT, EntityIdT, SessionT]
):
    builder: StatementBuilder

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.builder = StatementBuilder(None)

    def bulk_insert(
        self,
        session: SessionT,
        values: t.Sequence[t.Dict[str, t.Any]] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_insert(self.model, values)
        return session.execute(statement, execution_options=execution_options or {})

    def bulk_update(
        self,
        session: SessionT,
        conditions: t.Sequence[ColumnExpr] = (),
        values: t.Optional[t.Dict[str, t.Any]] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_update(self.model, conditions, values)
        return session.execute(statement, execution_options=execution_options or {})

    def bulk_delete(
        self,
        session: SessionT,
        conditions: t.Sequence[ColumnExpr] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_delete(self.model, conditions)
        return session.execute(statement, execution_options=execution_options or {})
