from __future__ import annotations

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
from quart_sqlalchemy.types import ORMOption
from quart_sqlalchemy.types import Selectable
from quart_sqlalchemy.types import SessionT


# from abc import abstractmethod


sa = sqlalchemy


class AbstractRepository(t.Generic[EntityT, EntityIdT], metaclass=ABCMeta):
    """A repository interface."""

    # identity: t.Type[EntityIdT]

    # def __init__(self, model: t.Type[EntityT]):
    #     self.model = model

    @property
    def model(self) -> t.Type[EntityT]:
        return self.__orig_class__.__args__[0]  # type: ignore

    @property
    def identity(self) -> t.Type[EntityIdT]:
        return self.__orig_class__.__args__[1]  # type: ignore


class AbstractBulkRepository(t.Generic[EntityT, EntityIdT], metaclass=ABCMeta):
    """A repository interface for bulk operations.

    Note: this interface circumvents ORM internals, breaking commonly expected behavior in order
    to gain performance benefits.  Only use this class whenever absolutely necessary.
    """

    @property
    def model(self) -> t.Type[EntityT]:
        return self.__orig_class__.__args__[0]  # type: ignore

    @property
    def identity(self) -> t.Type[EntityIdT]:
        return self.__orig_class__.__args__[1]  # type: ignore


class SQLAlchemyRepository(
    AbstractRepository[EntityT, EntityIdT],
    t.Generic[EntityT, EntityIdT],
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

    # session: sa.orm.Session
    builder: StatementBuilder

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # self.session = session
        self.builder = StatementBuilder(None)

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
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(self.model).where(self.model.id == id_).limit(1)  # type: ignore

        for option in options:
            statement = statement.options(option)

        if for_update:
            statement = statement.with_for_update()

        return session.scalars(statement, execution_options=execution_options).one_or_none()

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

        results = session.scalars(statement)
        if yield_by_chunk:
            results = results.partitions()
        return results

    def delete(
        self, session: sa.orm.Session, id_: EntityIdT, include_inactive: bool = False
    ) -> None:
        # if self.has_soft_delete:
        #     raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        entity = self.get(id_, include_inactive=include_inactive)
        if not entity:
            raise RuntimeError(f"Entity with id {id_} not found.")

        session.delete(entity)
        session.flush()

    def deactivate(self, session: sa.orm.Session, id_: EntityIdT) -> EntityT:
        # if not self.has_soft_delete:
        #     raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        return self.update(id_, dict(is_active=False))

    def reactivate(self, session: sa.orm.Session, id_: EntityIdT) -> EntityT:
        # if not self.has_soft_delete:
        #     raise RuntimeError("Can't delete entity that uses soft-delete semantics.")

        return self.update(id_, dict(is_active=False))

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
        selectable = sa.sql.literal(True)

        execution_options = {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(selectable).where(*conditions)  # type: ignore

        if for_update:
            statement = statement.with_for_update()

        result = session.execute(statement, execution_options=execution_options).scalar()

        return bool(result)


class SQLAlchemyBulkRepository(AbstractBulkRepository, t.Generic[SessionT, EntityT, EntityIdT]):
    def __init__(self, **kwargs: t.Any):
        super().__init__(**kwargs)
        self.builder = StatementBuilder(self.model)
        # session = session

    def bulk_insert(
        self,
        session: sa.orm.Session,
        values: t.Sequence[t.Dict[str, t.Any]] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_insert(self.model, values)
        return session.execute(statement, execution_options=execution_options or {})

    def bulk_update(
        self,
        session: sa.orm.Session,
        conditions: t.Sequence[ColumnExpr] = (),
        values: t.Optional[t.Dict[str, t.Any]] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_update(self.model, conditions, values)
        return session.execute(statement, execution_options=execution_options or {})

    def bulk_delete(
        self,
        session: sa.orm.Session,
        conditions: t.Sequence[ColumnExpr] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        statement = self.builder.bulk_delete(self.model, conditions)
        return session.execute(statement, execution_options=execution_options or {})
