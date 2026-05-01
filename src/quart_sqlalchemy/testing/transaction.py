import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio

if t.TYPE_CHECKING:
    from ..bind import AsyncBind, Bind

sa = sqlalchemy


class TestTransaction:
    bind: "Bind"
    connection: sa.Connection
    trans: sa.Transaction
    nested: sa.NestedTransaction | None = None

    def __init__(self, bind: "Bind", savepoint: bool = False):
        self.savepoint = savepoint
        self.bind = bind

    def Session(self, **options: t.Any) -> sa.orm.Session:
        options.update(bind=self.connection)
        if self.savepoint:
            options.update(join_transaction_mode="create_savepoint")
        return self.bind.Session(**options)

    def begin(self) -> None:
        self.connection = self.bind.engine.connect()
        self.trans = self.connection.begin()

        if self.savepoint:
            self.nested = self.connection.begin_nested()

    def close(self, exc: BaseException | None = None) -> None:
        exceptions: list[Exception] = []
        if exc and isinstance(exc, Exception):
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

    def __enter__(self) -> "TestTransaction":
        self.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        self.close(exc_val)

    def __repr__(self) -> str:
        if hasattr(self, "bind") and self.bind is not None:
            url = str(self.bind.url)
        else:
            url = "no app context"
        return f"<{type(self).__name__} {url}>"


class AsyncTestTransaction(TestTransaction):
    bind: "AsyncBind"
    connection: sa.ext.asyncio.AsyncConnection  # type: ignore[assignment]
    trans: sa.ext.asyncio.AsyncTransaction  # type: ignore[assignment]
    nested: sa.ext.asyncio.AsyncTransaction | None = None  # type: ignore[assignment]

    def __init__(self, bind: "AsyncBind", savepoint: bool = False):
        self.savepoint = savepoint
        self.bind = bind

    async def begin(self) -> None:  # type: ignore[override]
        self.connection = await self.bind.engine.connect().__aenter__()
        self.trans = await self.connection.begin()

        if self.savepoint:
            self.nested = await self.connection.begin_nested()

    async def close(self, exc: BaseException | None = None) -> None:  # type: ignore[override]
        exceptions: list[Exception] = []
        if exc and isinstance(exc, Exception):
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

    async def __aenter__(self) -> "AsyncTestTransaction":
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: t.Any,
    ) -> None:
        await self.close(exc_val)
