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
    if all(
        [
            isinstance(session_factory, sa.ext.asyncio.async_sessionmaker),
            "sync_session_class" in session_factory.kw,
        ]
    ):
        session_factory = session_factory.kw["sync_session_class"]

    setup_soft_delete_for_session(session_factory)  # type: ignore


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
