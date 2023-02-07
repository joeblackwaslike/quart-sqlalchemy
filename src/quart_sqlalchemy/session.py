from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from quart import abort
from quart.globals import app_ctx

from .pagination import AsyncSelectPagination
from .pagination import Pagination
from .pagination import SelectPagination
from .types import DataObjType
from .types import EntityType
from .types import IdentType
from .types import RowDataType


sa = sqlalchemy


if t.TYPE_CHECKING:
    from .extension import SQLAlchemy


def _clause_to_engine(
    clause: t.Optional[EntityType], engines: dict[t.Optional[str], sa.Engine]
) -> t.Optional[sa.Engine]:
    """If the clause is a table, return the engine associated with the table's
    metadata's bind key.
    """
    if isinstance(clause, sa.Table) and "bind_key" in clause.metadata.info:
        key = clause.metadata.info["bind_key"]

        if key not in engines:
            raise sa.exc.UnboundExecutionError(
                f"Bind key '{key}' is not in 'SQLALCHEMY_BINDS' config."
            )

        return engines[key]

    return None


class Session(sa.orm.Session, t.Generic[DataObjType]):
    """A SQLAlchemy :class:`~sqlalchemy.orm.Session` class that chooses what engine to
    use based on the bind key associated with the metadata associated with the thing
    being queried.

    To customize ``db.session``, subclass this and pass it as the ``class_`` key in the
    ``session_options`` to :class:`.SQLAlchemy`.

    .. versionchanged:: 3.0
        Renamed from ``SignallingSession``.
    """

    def __init__(self, db: SQLAlchemy, **kwargs):
        super().__init__(**kwargs)
        self._db = db
        self._model_changes: dict[object, tuple[t.Any, str]] = {}

    def get_bind(
        self,
        mapper: t.Optional[EntityType] = None,
        clause: t.Optional[EntityType] = None,
        bind: t.Optional[sa.Engine | sa.Connection] = None,
        **kwargs,
    ) -> sa.Engine | sa.Connection:
        engine = self._get_bind(mapper, clause, bind, **kwargs)

        if hasattr(engine, "sync_engine"):
            return engine.sync_engine
        return engine

    def _get_bind(
        self,
        mapper: t.Optional[EntityType] = None,
        clause: t.Optional[EntityType] = None,
        bind: t.Optional[sa.Engine | sa.Connection] = None,
        **kwargs,
    ) -> sa.Engine | sa.Connection:
        """Select an engine based on the ``bind_key`` of the metadata associated with
        the model or table being queried. If no bind key is set, uses the default bind.

        .. versionchanged:: 3.0.3
            Fix finding the bind for a joined inheritance model.

        .. versionchanged:: 3.0
            The implementation more closely matches the base SQLAlchemy implementation.

        .. versionchanged:: 2.1
            Support joining an external transaction.
        """
        if bind is not None:
            return bind

        engines = self._db.engines

        if mapper is not None:
            try:
                mapper = sa.inspect(mapper)
            except sa.exc.NoInspectionAvailable as e:
                if isinstance(mapper, type):
                    raise sa.orm.exc.UnmappedClassError(mapper) from e

                raise

            engine = _clause_to_engine(mapper.local_table, engines)
            if engine is not None:
                return engine

        if clause is not None:
            engine = _clause_to_engine(clause, engines)
            if engine is not None:
                return engine

        if None in engines:
            return engines[None]

        return super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)

    def get_or_404(
        self,
        entity: EntityType,
        ident: IdentType,
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> t.Optional[DataObjType]:
        """Like :meth:`session.get() <sqlalchemy.orm.Session.get>` but aborts with a
        ``404 Not Found`` error instead of returning ``None``.

        :param entity: The model class to query.
        :param ident: The primary key to query.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        value = self.get(entity, ident, **kwargs)

        if value is None:
            abort(404, description=description)

        return value

    def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> t.Optional[RowDataType]:
        """Like :meth:`Result.scalar() <sqlalchemy.engine.Result.scalar>`, but aborts
        with a ``404 Not Found`` error instead of returning ``None``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        value = self.execute(statement, **kwargs).scalar()

        if value is None:
            abort(404, description=description)

        return value

    def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> RowDataType:
        """Like :meth:`Result.scalar_one() <sqlalchemy.engine.Result.scalar_one>`,
        but aborts with a ``404 Not Found`` error instead of raising ``sa.exc.NoResultFound``
        or ``sa.exc.MultipleResultsFound``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        try:
            return self.execute(statement, **kwargs).scalar_one()
        except (sa.exc.NoResultFound, sa.exc.MultipleResultsFound):
            abort(404, description=description)

    def paginate(
        self,
        select: sa.sql.Select[t.Any],
        *,
        page: t.Optional[int] = None,
        per_page: t.Optional[int] = None,
        max_per_page: t.Optional[int] = None,
        error_out: bool = True,
        count: bool = True,
    ) -> Pagination:
        """Apply an offset and limit to a select statment based on the current page and
        number of items per page, returning a :class:`.Pagination` object.

        The statement should select a model class, like ``select(User)``. This applies
        ``unique()`` and ``scalars()`` modifiers to the result, so compound selects will
        not return the expected results.

        :param select: The ``select`` statement to paginate.
        :param page: The current page, used to calculate the offset. Defaults to the
            ``page`` query arg during a request, or 1 otherwise.
        :param per_page: The maximum number of items on a page, used to calculate the
            offset and limit. Defaults to the ``per_page`` query arg during a request,
            or 20 otherwise.
        :param max_per_page: The maximum allowed value for ``per_page``, to limit a
            user-provided value. Use ``None`` for no limit. Defaults to 100.
        :param error_out: Abort with a ``404 Not Found`` error if no items are returned
            and ``page`` is not 1, or if ``page`` or ``per_page`` is less than 1, or if
            either are not ints.
        :param count: Calculate the total number of values by issuing an extra count
            query. For very complex queries this may be inaccurate or slow, so it can be
            disabled and set manually if necessary.

        .. versionchanged:: 3.0
            The ``count`` query is more efficient.

        .. versionadded:: 3.0
        """
        return SelectPagination(
            select=select,
            session=self,
            page=page,
            per_page=per_page,
            max_per_page=max_per_page,
            error_out=error_out,
            count=count,
        ).get_items()


class scoped_session(sa.orm.scoped_session, t.Generic[DataObjType]):
    def get_or_404(
        self,
        entity: EntityType,
        ident: IdentType,
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> t.Optional[DataObjType]:
        return self._proxied.get_or_404(entity, ident, description=description, **kwargs)

    def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> t.Optional[RowDataType]:
        return self._proxied.first_or_404(statement, description=description, **kwargs)

    def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> RowDataType:
        return self._proxied.one_or_404(statement, description=description, **kwargs)

    def paginate(
        self,
        select: sa.sql.Select[t.Any],
        *,
        page: t.Optional[int] = None,
        per_page: t.Optional[int] = None,
        max_per_page: t.Optional[int] = None,
        error_out: bool = True,
        count: bool = True,
    ) -> Pagination:
        return self._proxied.paginate(
            select,
            page=page,
            per_page=per_page,
            max_per_page=max_per_page,
            error_out=error_out,
            count=count,
        )

    def using_bind(self, name: str):
        return self._proxied.using_bind(name)


class AsyncSession(sa.ext.asyncio.AsyncSession, t.Generic[DataObjType]):
    async def get_or_404(
        self,
        entity: EntityType,
        ident: IdentType,
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> t.Optional[DataObjType]:
        """Like :meth:`session.get() <sqlalchemy.orm.Session.get>` but aborts with a
        ``404 Not Found`` error instead of returning ``None``.

        :param entity: The model class to query.
        :param ident: The primary key to query.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        value = await self.get(entity, ident, **kwargs)

        if value is None:
            abort(404, description=description)

        return value

    async def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> t.Optional[RowDataType]:
        """Like :meth:`Result.scalar() <sqlalchemy.engine.Result.scalar>`, but aborts
        with a ``404 Not Found`` error instead of returning ``None``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        value = (await self.execute(statement, **kwargs)).scalar()

        if value is None:
            abort(404, description=description)

        return value

    async def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> RowDataType:
        """Like :meth:`Result.scalar_one() <sqlalchemy.engine.Result.scalar_one>`,
        but aborts with a ``404 Not Found`` error instead of raising ``sa.exc.NoResultFound``
        or ``sa.exc.MultipleResultsFound``.

        :param statement: The ``select`` statement to execute.
        :param description: A custom message to show on the error page.

        .. versionadded:: 3.0
        """
        try:
            return (await self.execute(statement, **kwargs)).scalar_one()
        except (sa.exc.NoResultFound, sa.exc.MultipleResultsFound):
            abort(404, description=description)

    async def paginate(
        self,
        select: sa.sql.Select[t.Any],
        *,
        page: t.Optional[int] = None,
        per_page: t.Optional[int] = None,
        max_per_page: t.Optional[int] = None,
        error_out: bool = True,
        count: bool = True,
    ) -> Pagination:
        """Apply an offset and limit to a select statment based on the current page and
        number of items per page, returning a :class:`.Pagination` object.

        The statement should select a model class, like ``select(User)``. This applies
        ``unique()`` and ``scalars()`` modifiers to the result, so compound selects will
        not return the expected results.

        :param select: The ``select`` statement to paginate.
        :param page: The current page, used to calculate the offset. Defaults to the
            ``page`` query arg during a request, or 1 otherwise.
        :param per_page: The maximum number of items on a page, used to calculate the
            offset and limit. Defaults to the ``per_page`` query arg during a request,
            or 20 otherwise.
        :param max_per_page: The maximum allowed value for ``per_page``, to limit a
            user-provided value. Use ``None`` for no limit. Defaults to 100.
        :param error_out: Abort with a ``404 Not Found`` error if no items are returned
            and ``page`` is not 1, or if ``page`` or ``per_page`` is less than 1, or if
            either are not ints.
        :param count: Calculate the total number of values by issuing an extra count
            query. For very complex queries this may be inaccurate or slow, so it can be
            disabled and set manually if necessary.

        .. versionchanged:: 3.0
            The ``count`` query is more efficient.

        .. versionadded:: 3.0
        """
        pager = AsyncSelectPagination(
            select=select,
            session=self,
            page=page,
            per_page=per_page,
            max_per_page=max_per_page,
            error_out=error_out,
            count=count,
        )
        return await pager.get_items()


class async_scoped_session(sa.ext.asyncio.async_scoped_session, t.Generic[DataObjType]):
    async def get_or_404(
        self,
        entity: EntityType,
        ident: IdentType,
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> t.Optional[DataObjType]:
        return await self._proxied.get_or_404(entity, ident, description=description, **kwargs)

    async def first_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs: t.Any,
    ) -> t.Optional[RowDataType]:
        return await self._proxied.first_or_404(statement, description=description, **kwargs)

    async def one_or_404(
        self,
        statement: sa.sql.Select[t.Any],
        *,
        description: t.Optional[str] = None,
        **kwargs,
    ) -> RowDataType:
        return await self._proxied.one_or_404(statement, description=description, **kwargs)

    async def paginate(
        self,
        select: sa.sql.Select[t.Any],
        *,
        page: t.Optional[int] = None,
        per_page: t.Optional[int] = None,
        max_per_page: t.Optional[int] = None,
        error_out: bool = True,
        count: bool = True,
    ) -> Pagination:
        return await self._proxied.paginate(
            select,
            page=page,
            per_page=per_page,
            max_per_page=max_per_page,
            error_out=error_out,
            count=count,
        )

    def using_bind(self, name: str):
        return self._proxied.using_bind(name)


class RoutingSessionMixin:
    _bind_name: t.Optional[str] = None

    def get_bind(
        self,
        mapper: t.Optional[EntityType] = None,
        clause: t.Optional[EntityType] = None,
        bind: t.Optional[sa.Engine | sa.Connection] = None,
        **kwargs,
    ) -> sa.Engine | sa.Connection | sa.ext.asyncio.AsyncEngine | sa.ext.asyncio.AsyncConnection:
        if self.bind is not None:
            return self.bind

        if self._db is not None and self._bind_name is not None:
            engines = self._db.engines
            engine = engines[self._bind_name]
            return engine

        return super().get_bind(mapper, clause, bind, **kwargs)

    def using_bind(self, name: str):
        bind_session = RoutingSession(self._db)

        new_vars = vars(bind_session)
        old_vars = vars(self)
        new_vars.update(old_vars)

        bind_session._bind_name = name
        return bind_session


class RoutingSession(RoutingSessionMixin, Session):
    pass


def _app_ctx_id() -> int:
    """Get the id of the current Quart application context for the session scope."""
    return id(app_ctx._get_current_object())  # type: ignore[attr-defined]
