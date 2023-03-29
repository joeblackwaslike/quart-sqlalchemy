from __future__ import annotations

import os
import typing as t
from contextlib import contextmanager

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util

from . import signals
from .config import BindConfig
from .model import setup_soft_delete_for_session
from .testing import AsyncTestTransaction
from .testing import TestTransaction


sa = sqlalchemy


class BindBase:
    config: BindConfig
    metadata: sa.MetaData
    engine: sa.Engine
    Session: sa.orm.sessionmaker

    def __init__(
        self,
        config: BindConfig,
        metadata: sa.MetaData,
    ):
        self.config = config
        self.metadata = metadata

    @property
    def url(self) -> str:
        if not hasattr(self, "engine"):
            raise RuntimeError("Database not initialized yet. Call initialize() first.")
        return str(self.engine.url)

    @property
    def is_async(self) -> bool:
        if not hasattr(self, "engine"):
            raise RuntimeError("Database not initialized yet. Call initialize() first.")
        return self.engine.url.get_dialect().is_async

    @property
    def is_read_only(self):
        return self.config.read_only


class BindContext(BindBase):
    pass


class Bind(BindBase):
    def __init__(
        self,
        config: BindConfig,
        metadata: sa.MetaData,
        initialize: bool = True,
    ):
        self.config = config
        self.metadata = metadata

        if initialize:
            self.initialize()

    def initialize(self):
        if hasattr(self, "engine"):
            self.engine.dispose()

        self.engine = self.create_engine(
            self.config.engine.dict(exclude_unset=True, exclude_none=True),
            prefix="",
        )
        self.Session = self.create_session_factory(
            self.config.session.dict(exclude_unset=True, exclude_none=True),
        )
        return self

    @contextmanager
    def context(
        self,
        engine_execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        session_execution__options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> t.Generator[BindContext, None, None]:
        context = BindContext(self.config, self.metadata)
        context.engine = self.engine.execution_options(**engine_execution_options or {})
        context.Session = self.create_session_factory(session_execution__options or {})
        context.Session.configure(bind=context.engine)

        signals.bind_context_entered.send(
            self,
            engine_execution_options=engine_execution_options,
            session_execution__options=session_execution__options,
            context=context,
        )
        yield context

        signals.bind_context_exited.send(
            self,
            engine_execution_options=engine_execution_options,
            session_execution__options=session_execution__options,
            context=context,
        )

    def create_session_factory(
        self, options: dict[str, t.Any]
    ) -> sa.orm.sessionmaker[sa.orm.Session]:
        signals.before_bind_session_factory_created.send(self, options=options)
        session_factory = sa.orm.sessionmaker(bind=self.engine, **options)
        signals.after_bind_session_factory_created.send(
            self, options=options, session_factory=session_factory
        )
        return session_factory

    def create_engine(self, config: t.Dict[str, t.Any], prefix: str = "") -> sa.Engine:
        signals.before_bind_engine_created.send(self, config=config, prefix=prefix)
        engine = sa.engine_from_config(config, prefix=prefix)
        signals.after_bind_engine_created.send(self, config=config, prefix=prefix, engine=engine)
        return engine

    def test_transaction(self, savepoint: bool = False):
        return TestTransaction(self, savepoint=savepoint)

    def _call_metadata(self, method: str):
        with self.engine.connect() as conn:
            with conn.begin():
                return getattr(self.metadata, method)(bind=conn)

    def create_all(self):
        return self._call_metadata("create_all")

    def drop_all(self):
        return self._call_metadata("drop_all")

    def reflect(self):
        return self._call_metadata("reflect")

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.engine.url}>"


class AsyncBind(Bind):
    engine: sa.ext.asyncio.AsyncEngine
    Session: sa.ext.asyncio.async_sessionmaker

    def create_session_factory(
        self, options: dict[str, t.Any]
    ) -> sa.ext.asyncio.async_sessionmaker[sa.ext.asyncio.AsyncSession]:
        """
        It took some research to figure out the following trick which combines sync and async
        sessionmakers to make the async_sessionmaker a valid target for sqlalchemy events.

        Details can be found at:
        https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#examples-of-event-listeners-with-async-engines-sessions-sessionmakers
        """
        signals.before_bind_session_factory_created.send(self, options=options)

        sync_sessionmaker = sa.orm.sessionmaker()
        session_factory = sa.ext.asyncio.async_sessionmaker(
            bind=self.engine,
            sync_session_class=sync_sessionmaker,
            **options,
        )

        signals.after_bind_session_factory_created.send(
            self, options=options, session_factory=session_factory
        )
        return session_factory

    def create_engine(
        self, config: dict[str, t.Any], prefix: str = ""
    ) -> sa.ext.asyncio.AsyncEngine:
        signals.before_bind_engine_created.send(self, config=config, prefix=prefix)
        engine = sa.ext.asyncio.async_engine_from_config(config, prefix=prefix)
        signals.after_bind_engine_created.send(self, config=config, prefix=prefix, engine=engine)
        return engine

    def test_transaction(self, savepoint: bool = False):
        return AsyncTestTransaction(self, savepoint=savepoint)

    async def _call_metadata(self, method: str):
        async with self.engine.connect() as conn:
            async with conn.begin():

                def sync_call(conn: sa.Connection, method: str):
                    getattr(self.metadata, method)(bind=conn)

                return await conn.run_sync(sync_call, method)


@signals.after_bind_session_factory_created.connect
def register_soft_delete_support_for_session(
    bind: t.Union[Bind, AsyncBind],
    options: t.Dict[str, t.Any],
    session_factory: t.Union[sa.orm.sessionmaker, sa.ext.asyncio.async_sessionmaker],
) -> None:
    """Register the event handlers that enable soft-delete logic to be applied automatically.

    This functionality is opt-in by nature.  Opt-in involves adding the SoftDeleteMixin to the
    ORM models that should support soft-delete.  You can learn more by checking out the
    model.mixins module.
    """
    if all(
        [
            isinstance(session_factory, sa.ext.asyncio.async_sessionmaker),
            "sync_session_class" in session_factory.kw,
        ]
    ):
        session_factory = session_factory.kw["sync_session_class"]

    setup_soft_delete_for_session(session_factory)  # type: ignore


# Beware of Dragons!
#
# The following handlers aren't at all crucial to understanding how this package works, they are
# mostly based on well known sqlalchemy recipes and their impact can be fully understood from
# their docstrings alone.


@signals.after_bind_engine_created.connect
def register_engine_connection_cross_process_safety_handlers(
    sender: Bind,
    config: t.Dict[str, t.Any],
    prefix: str,
    engine: t.Union[sa.Engine, sa.ext.asyncio.AsyncEngine],
) -> None:
    """Register event handlers to invalidate connections shared across process boundaries.

    SQLAlchemy connections aren't safe to share across processes and most sqlalchemy engines
    contain a connection pool full of them.  This will cause issues when these connections are
    used concurrently in multiple processes that are bizarre and become difficult to trace the
    origin of.  This quart application utilizes multiple processes, one for each API worker,
    typically handled by the ASGI server, in our case hypercorn.  Another place where we run into
    multiple processes is during testing.  We use the pytest-xdist plugin to split our tests
    across multiple cores and drastically reduce the time required to complete.

    Both of these use cases dictate our application needs to be concerned with what objects
    could possibly be shared across processes and follow any recommendations made concerning
    that library/service around process forking/spawning.  Usually the only resources we need
    to worry about are file descriptors (including sockets and network connections).

    SQLAlchemy has a section of their docs dedicated to this exact concern, see that page for
    more details: https://docs.sqlalchemy.org/en/20/core/pooling.html#pooling-multiprocessing
    """

    # Use the sync_engine when AsyncEngine
    if isinstance(engine, sa.ext.asyncio.AsyncEngine):
        engine = engine.sync_engine

    def close_connections_for_forking():
        engine.dispose(close=False)

    os.register_at_fork(before=close_connections_for_forking)

    def connect(dbapi_connection, connection_record):
        connection_record.info["pid"] = os.getpid()

    if not sa.event.contains(engine, "connect", connect):
        sa.event.listen(engine, "connect", connect)

    def checkout(dbapi_connection, connection_record, connection_proxy):
        pid = os.getpid()
        if connection_record.info["pid"] != pid:
            connection_record.dbapi_connection = connection_proxy.dbapi_connection = None
            raise sa.exc.DisconnectionError(
                "Connection record belongs to pid {}, attempting to check out in pid {}".format(
                    connection_record.info["pid"], pid
                )
            )

    if not sa.event.contains(engine, "checkout", checkout):
        sa.event.listen(engine, "checkout", checkout)


@signals.after_bind_engine_created.connect
def register_engine_connection_sqlite_specific_transaction_fix(
    sender: Bind,
    config: t.Dict[str, t.Any],
    prefix: str,
    engine: t.Union[sa.Engine, sa.ext.asyncio.AsyncEngine],
) -> None:
    """Register event handlers to fix dbapi broken transaction for sqlite dialects.

    The pysqlite DBAPI driver has several long-standing bugs which impact the correctness of its
    transactional behavior. In its default mode of operation, SQLite features such as
    SERIALIZABLE isolation, transactional DDL, and SAVEPOINT support are non-functional, and in
    order to use these features, workarounds must be taken.

    The issue is essentially that the driver attempts to second-guess the user’s intent, failing
    to start transactions and sometimes ending them prematurely, in an effort to minimize the
    SQLite databases’s file locking behavior, even though SQLite itself uses “shared” locks for
    read-only activities.

    SQLAlchemy chooses to not alter this behavior by default, as it is the long-expected behavior
    of the pysqlite driver; if and when the pysqlite driver attempts to repair these issues, that
    will be more of a driver towards defaults for SQLAlchemy.

    The good news is that with a few events, we can implement transactional support fully, by
    disabling pysqlite’s feature entirely and emitting BEGIN ourselves. This is achieved using
    two event listeners:

    To learn more about this recipe, check out the sqlalchemy docs link below:
        https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#pysqlite-serializable
    """

    # Use the sync_engine when AsyncEngine
    if isinstance(engine, sa.ext.asyncio.AsyncEngine):
        engine = engine.sync_engine

    if engine.dialect.name != "sqlite":
        return

    def do_connect(dbapi_connection, connection_record):
        # disable pysqlite's emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        dbapi_connection.isolation_level = None

    if not sa.event.contains(engine, "connect", do_connect):
        sa.event.listen(engine, "connect", do_connect)

    def do_begin(conn_):
        # emit our own BEGIN
        conn_.exec_driver_sql("BEGIN")

    if not sa.event.contains(engine, "begin", do_begin):
        sa.event.listen(engine, "begin", do_begin)
