import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from exceptiongroup import ExceptionGroup


if t.TYPE_CHECKING:
    from ..bind import AsyncBind
    from ..bind import Bind

sa = sqlalchemy


class TestTransaction:
    bind: "Bind"
    connection: sa.Connection
    trans: sa.Transaction
    nested: t.Optional[sa.NestedTransaction] = None

    def __init__(self, bind: "Bind", savepoint: bool = False):
        self.savepoint = savepoint
        self.bind = bind

    def Session(self, **options):
        options.update(bind=self.connection)
        if self.savepoint:
            options.update(join_transaction_mode="create_savepoint")
        return self.bind.Session(**options)

    def begin(self):
        self.connection = self.bind.engine.connect()
        self.trans = self.connection.begin()

        if self.savepoint:
            self.nested = self.connection.begin_nested()

    def close(self, exc: t.Optional[Exception] = None) -> None:
        exceptions = []
        if exc:
            exceptions.append(exc)

        if hasattr(self, "nested"):
            try:
                self.trans.rollback()
            except Exception as trans_err:
                exceptions.append(trans_err)

        if hasattr(self, "connection"):
            try:
                self.connection.close()
            except Exception as conn_err:
                exceptions.append(conn_err)

        if exceptions:
            raise ExceptionGroup(
                f"Exceptions were raised inside a {type(self).__name__}", exceptions
            )

    def __enter__(self):
        self.begin()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close(exc_val)

    def __repr__(self):
        if hasattr(self, "bind") and self.bind is not None:
            url = str(self.bind.url)
        else:
            url = "no app context"
        return f"<{type(self).__name__} {url}>"


class AsyncTestTransaction(TestTransaction):
    bind: "AsyncBind"
    connection: sa.ext.asyncio.AsyncConnection
    trans: sa.ext.asyncio.AsyncTransaction
    nested: t.Optional[sa.ext.asyncio.AsyncTransaction] = None

    def __init__(self, bind: "AsyncBind", savepoint: bool = False):
        super().__init__(bind, savepoint=savepoint)

    async def begin(self):
        self.connection = await self.bind.engine.connect()
        self.trans = await self.connection.begin()

        if self.savepoint:
            self.nested = await self.connection.begin_nested()

    async def close(self, exc: t.Optional[Exception] = None) -> None:
        exceptions = []
        if exc:
            exceptions.append(exc)

        if hasattr(self, "nested"):
            try:
                await self.trans.rollback()
            except Exception as trans_err:
                exceptions.append(trans_err)

        if hasattr(self, "connection"):
            try:
                await self.connection.close()
            except Exception as conn_err:
                exceptions.append(conn_err)

        if exceptions:
            raise ExceptionGroup(
                f"Exceptions were raised inside a {type(self).__name__}", exceptions
            )

    async def __aenter__(self):
        await self.begin()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close(exc_val)
