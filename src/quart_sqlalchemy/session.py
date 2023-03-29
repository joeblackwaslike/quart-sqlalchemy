from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from quart import abort
from sqlapagination import KeySetPage
from sqlapagination import KeySetPaginator

from .types import EntityIdT
from .types import EntityT
from .types import ORMOption


sa = sqlalchemy


class Session(sa.orm.Session, t.Generic[EntityT, EntityIdT]):
    """A SQLAlchemy :class:`~sqlalchemy.orm.Session` class.

    To customize ``db.session``, subclass this and pass it as the ``class_`` key in the
    ``session_options``.
    """

    def get_or_404(
        self,
        entity: EntityT,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        for_update: bool = False,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> EntityT:
        """Like :meth:`session.get() <sqlalchemy.orm.Session.get>` but aborts with a
        ``404 Not Found`` error instead of returning ``None``.

        :param entity: The model class to query.
        :param id_: The primary key to query.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(self.model).where(self.model.id == id_).limit(1)  # type: ignore

        for option in options:
            statement = statement.options(option)

        if for_update:
            statement = statement.with_for_update()

        result = self.scalars(statement, execution_options=execution_options).one_or_none()

        if result is None:
            abort(404, description=description)

        return result

    def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> EntityT:
        """Like :meth:`Result.scalar() <sqlalchemy.engine.Result.scalar>`, but aborts
        with a ``404 Not Found`` error instead of returning ``None``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        result = self.scalars(statement, execution_options=execution_options, **kwargs).first()

        if result is None:
            abort(404, description=description)

        return result

    def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> EntityT:
        """Like :meth:`Result.scalar_one() <sqlalchemy.engine.Result.scalar_one>`,
        but aborts with a ``404 Not Found`` error instead of raising ``sa.exc.NoResultFound``
        or ``sa.exc.MultipleResultsFound``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        try:
            return self.scalars(statement, execution_options=execution_options, **kwargs).one()
        except (sa.exc.NoResultFound, sa.exc.MultipleResultsFound):
            abort(404, description=description)

    def paginate(
        self,
        selectable: sa.sql.Select[t.Any],
        page_size: int = 10,
        bookmark: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> KeySetPage:
        """Apply keyset pagination to a select statment based on the current page and
        number of items per page, returning a :class:`.KeySetPage` object.

        The statement should select a model class, like ``select(User)``, and have
        an order_by clause containing a key unique to the table.  The easiest way to
        achieve the latter is ensure the order_by clause contains the primary_key as
        the last column.

        WARNING: Not yet tested, experimental, use with caution!
        """
        paginator = KeySetPaginator(
            selectable,
            page_size=page_size,
            bookmark=bookmark,
        )
        statement = paginator.get_modified_sql_statement()
        result = self.scalars(statement).all()
        return paginator.parse_result(result)


class AsyncSession(sa.ext.asyncio.AsyncSession, t.Generic[EntityT]):
    async def get_or_404(
        self,
        entity: EntityT,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        for_update: bool = False,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> EntityT:
        """Like :meth:`session.get() <sqlalchemy.orm.Session.get>` but aborts with a
        ``404 Not Found`` error instead of returning ``None``.

        :param entity: The model class to query.
        :param id_: The primary key to query.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        statement = sa.select(self.model).where(self.model.id == id_).limit(1)  # type: ignore

        for option in options:
            statement = statement.options(option)

        if for_update:
            statement = statement.with_for_update()

        result = (await self.scalars(statement, execution_options=execution_options)).one_or_none()

        if result is None:
            abort(404, description=description)

        return result

    async def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> EntityT:
        """Like :meth:`Result.scalar() <sqlalchemy.engine.Result.scalar>`, but aborts
        with a ``404 Not Found`` error instead of returning ``None``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        result = (
            await self.scalars(statement, execution_options=execution_options, **kwargs)
        ).first()

        if result is None:
            abort(404, description=description)

        return result

    async def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        include_inactive: bool = False,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> EntityT:
        """Like :meth:`Result.scalar_one() <sqlalchemy.engine.Result.scalar_one>`,
        but aborts with a ``404 Not Found`` error instead of raising ``sa.exc.NoResultFound``
        or ``sa.exc.MultipleResultsFound``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        execution_options = execution_options or {}
        if include_inactive:
            execution_options.setdefault("include_inactive", include_inactive)

        try:
            return (
                await self.scalars(statement, execution_options=execution_options, **kwargs)
            ).one()
        except (sa.exc.NoResultFound, sa.exc.MultipleResultsFound):
            abort(404, description=description)

    async def paginate(
        self,
        selectable: sa.sql.Select[t.Any],
        page_size: int = 10,
        bookmark: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> KeySetPage:
        """Apply keyset pagination to a select statment based on the current page and
        number of items per page, returning a :class:`.KeySetPage` object.

        The statement should select a model class, like ``select(User)``, and have
        an order_by clause containing a key unique to the table.  The easiest way to
        achieve the latter is ensure the order_by clause contains the primary_key as
        the last column.

        WARNING: Not yet tested, experimental, use with caution!
        """
        paginator = KeySetPaginator(
            selectable,
            page_size=page_size,
            bookmark=bookmark,
        )
        statement = paginator.get_modified_sql_statement()
        result = (await self.scalars(statement)).all()
        return paginator.parse_result(result)
