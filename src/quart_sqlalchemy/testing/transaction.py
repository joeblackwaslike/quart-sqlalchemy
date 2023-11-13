# This package is not finished

import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm


sa = sqlalchemy

if t.TYPE_CHECKING:
    from ..extension import SQLAlchemy


class TestTransactionBase:
    """Helper for building sessions that rollback everyting at the end.
    See ["Joining a Session into an External Transaction"](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html#session-external-transaction)
    in the SQLAlchemy documentation.
    """

    def __init__(
        self,
        db: "SQLAlchemy",
        bind_key: t.Optional[str] = None,
        savepoint: bool = False,
    ) -> None:
        self.db = db
        self.bind_key = bind_key
        self.savepoint = savepoint

    def __repr__(self):
        if hasattr(self, "engine"):
            url = str(self.engine.url)
        else:
            url = "no app context"
        return f"<{type(self).__name__} {url}>"


class SyncTestTransaction(TestTransactionBase):
    def close(self) -> None:
        # self.db.session.registry.clear()
        if hasattr(self, "_prev_scoped_session"):
            self.db.session = self._prev_scoped_session
            del self._prev_scoped_session

        if hasattr(self, "session"):
            self.session.close()

        if hasattr(self, "nested"):
            self.trans.rollback()

        if hasattr(self, "connection"):
            self.connection.close()

        if hasattr(self, "Session"):
            self.Session.remove()

    @property
    def aio(self):
        return AsyncTestTransaction(self.db, self.bind_key, self.savepoint)

    def start_transaction(self):
        self.engine = self.db.engines[self.bind_key]
        self.connection = self.engine.connect()

        self.trans = self.connection.begin()

        session_options = dict(**self.db._session_options, bind=self.connection)
        if self.savepoint:
            session_options.update(join_transaction_mode="create_savepoint")

        self.Session = self.db._make_scoped_session(session_options)
        self.session = self.Session()

        self._prev_scoped_session, self.db.session = self.db.session, self.Session

        if self.savepoint:
            self.nested = self.connection.begin_nested()

    def __enter__(self):
        self.start_transaction()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncTestTransaction(TestTransactionBase):
    async def start_transaction(self):
        self.engine = t.cast(sa.ext.asyncio.AsyncEngine, self.db.engines[self.bind_key])
        self.connection = await self.engine.connect()

        self.trans = await self.connection.begin()

        session_options = dict(**self.db._session_options, bind=self.connection)
        if self.savepoint:
            session_options.update(join_transaction_mode="create_savepoint")

        self.Session = self.db._make_scoped_session(session_options)
        self.session = await self.Session()

        self._prev_scoped_session, self.db.session = self.db.session, self.Session

        if self.savepoint:
            self.nested = await self.connection.begin_nested()

    async def close(self) -> None:
        # self.db.session.registry.clear()

        if hasattr(self, "_prev_scoped_session"):
            self.db.session = self._prev_scoped_session
            del self._prev_scoped_session

        if hasattr(self, "session"):
            await self.session.close()

        if hasattr(self, "nested"):
            await self.trans.rollback()

        if hasattr(self, "connection"):
            await self.connection.close()

        if hasattr(self, "Session"):
            await self.Session.remove()
