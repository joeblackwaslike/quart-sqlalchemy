from __future__ import annotations

import os
import threading
import typing as t
from contextlib import asynccontextmanager
from contextlib import contextmanager
from contextlib import ExitStack
from weakref import WeakValueDictionary

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
import typing_extensions as tx

from . import signals
from .config import BindConfig
from .model import setup_soft_delete_for_session
from .testing import AsyncTestTransaction
from .testing import TestTransaction


sa = sqlalchemy

SqlAMode = tx.Literal["orm", "core"]


class BindNotInitialized(RuntimeError):
    """ "Bind not initialized yet."""


class BindBase:
    name: t.Optional[str]
    url: sa.URL
    config: BindConfig
    metadata: sa.MetaData
    engine: sa.Engine
    Session: sa.orm.sessionmaker

    def __init__(
        self,
        name: t.Optional[str] = None,
        url: t.Union[sa.URL, str] = "sqlite://",
        config: t.Optional[BindConfig] = None,
        metadata: t.Optional[sa.MetaData] = None,
    ):
        self.name = name
        self.url = sa.make_url(url)
        self.config = config or BindConfig.default()
        self.metadata = metadata or sa.MetaData()

    @property
    def is_async(self) -> bool:
        return self.url.get_dialect().is_async

    @property
    def is_read_only(self) -> bool:
        return self.config.read_only

    def __repr__(self) -> str:
        parts = [type(self).__name__]
        if self.name:
            parts.append(self.name)
        if self.url:
            parts.append(str(self.url))
        if self.is_read_only:
            parts.append("[read-only]")

        return f"<{' '.join(parts)}>"


class BindContext(BindBase):
    pass


class Bind(BindBase):
    lock: threading.Lock
    _instances: WeakValueDictionary = WeakValueDictionary()

    def __init__(
        self,
        name: t.Optional[str] = None,
        url: t.Union[sa.URL, str] = "sqlite://",
        config: t.Optional[BindConfig] = None,
        metadata: t.Optional[sa.MetaData] = None,
        initialize: bool = True,
        track_instance: bool = False,
    ):
        super().__init__(name, url, config, metadata)
        self._initialization_lock = threading.Lock()

        if track_instance:
            self._track_instance(name)

        if initialize:
            self.initialize()

        self._session_stack = []

    def initialize(self) -> tx.Self:
        with self._initialization_lock:
            if hasattr(self, "engine"):
                self.engine.dispose()

            engine_config = self.config.engine.dict(exclude_unset=True, exclude_none=True)
            engine_config.setdefault("url", self.url)
            self.engine = self.create_engine(engine_config, prefix="")

            session_options = self.config.session.dict(exclude_unset=True, exclude_none=True)
            self.Session = self.create_session_factory(session_options)
        return self

    def _track_instance(self, name):
        if name is None:
            return

        if name in Bind._instances:
            raise ValueError("Bind instance `{name}` already exists, use another name.")
        else:
            Bind._instances[name] = self

    @classmethod
    def get_instance(cls, name: str = "default") -> Bind:
        """Get the singleton instance having `name`.

        This enables some really cool patterns similar to how logging allows getting an already
        initialized logger from anywhere without importing it directly.  Features like this are
        most useful when working in web frameworks like flask and quart that are more prone to
        circular dependency issues.

        Example:
            app/db.py:
                from quart_sqlalchemy import Bind

                default = Bind("default", url="sqlite://")

                with default.Session() as session:
                    with session.begin():
                        session.add(User())


            app/views/v1/user/login.py
                from quart_sqlalchemy import Bind

                # get the same `default` bind already instantiated in app/db.py
                default = Bind.get_instance("default")

                with default.Session() as session:
                    with session.begin():
                        session.add(User())
                ...
        """
        try:
            return Bind._instances[name]()
        except KeyError as err:
            raise ValueError(f"Bind instance `{name}` does not exist.") from err

    @t.overload
    @contextmanager
    def transaction(self, mode: SqlAMode = "orm") -> t.Generator[sa.orm.Session, None, None]:
        ...

    @t.overload
    @contextmanager
    def transaction(self, mode: SqlAMode = "core") -> t.Generator[sa.Connection, None, None]:
        ...

    @contextmanager
    def transaction(
        self, mode: SqlAMode = "orm"
    ) -> t.Generator[t.Union[sa.orm.Session, sa.Connection], None, None]:
        if mode == "orm":
            with self.Session() as session:
                with session.begin():
                    yield session
        elif mode == "core":
            with self.engine.connect() as connection:
                with connection.begin():
                    yield connection
        else:
            raise ValueError(f"Invalid transaction mode `{mode}`")

    def test_transaction(self, savepoint: bool = False) -> TestTransaction:
        return TestTransaction(self, savepoint=savepoint)

    @contextmanager
    def context(
        self,
        engine_execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        session_execution__options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> t.Generator[BindContext, None, None]:
        context = BindContext(f"{self.name}-context", self.url, self.config, self.metadata)
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
        self, options: t.Dict[str, t.Any]
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


class AsyncBind(Bind):
    engine: sa.ext.asyncio.AsyncEngine
    Session: sa.ext.asyncio.async_sessionmaker

    @asynccontextmanager
    async def transaction(self, mode: SqlAMode = "orm"):
        if mode == "orm":
            async with self.Session() as session:
                async with session.begin():
                    yield session
        elif mode == "core":
            async with self.engine.connect() as connection:
                async with connection.begin():
                    yield connection
        else:
            raise ValueError(f"Invalid transaction mode `{mode}`")

    def test_transaction(self, savepoint: bool = False):
        return AsyncTestTransaction(self, savepoint=savepoint)

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
