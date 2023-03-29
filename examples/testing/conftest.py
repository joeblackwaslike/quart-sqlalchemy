"""Pytest plugin for quart-sqlalchemy.

The lifecycle of the database during testing should look something like this.

1. The QuartSQLAlchemy object is instantiated by the application in a well known location such as the top level package.  Usually named `db`.  The database should be a fresh, in-memory, sqlite instance.
2. The Quart object is instantiated in a pytest fixture `app` using the application factory pattern, inside this factory, db.init_app(app) is called.
3. The database schema or DDL is executed using something like `db.create_all()`.
4. The necessary database test fixtures are loaded into the database.
5. A test transaction is created with savepoint, this transaction should be scoped at the `function` level.
6. Any calls to Session() should be patched to return a session bound to the test transaction savepoint.
    a. Bind.Session: sessionmaker
    b. BindContext.Session
    c. TestTransaction.Session (already patched)
7. Engine should be patched to return connections bound to the savepoint transaction but this is too complex to be in scope.
8. The test is run.
9. The test transaction goes out of function scope and rolls back the database.
10. The test transaction is recreated for the next test and so on until the pytest session is closed.
"""

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart


sa = sqlalchemy

from quart_sqlalchemy import AsyncBind
from quart_sqlalchemy import Base
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy
from quart_sqlalchemy.testing import AsyncTestTransaction
from quart_sqlalchemy.testing import TestTransaction


default_app = Quart(__name__)


@pytest.fixture(scope="session")
def app() -> Quart:
    """
    This pytest fixture should return the Quart object
    """
    return default_app


@pytest.fixture(scope="session")
def db_config() -> SQLAlchemyConfig:
    """
    This pytest fixture should return the SQLAlchemyConfig object
    """
    return SQLAlchemyConfig(
        model_class=Base,
        binds={  # type: ignore
            "default": {
                "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
                "session": {"expire_on_commit": False},
            },
            "read-replica": {
                "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
                "session": {"expire_on_commit": False},
                "read_only": True,
            },
            "async": {
                "engine": {
                    "url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"
                },
                "session": {"expire_on_commit": False},
            },
        },
    )


@pytest.fixture(scope="session")
@pytest.fixture
def _db(db_config: SQLAlchemyConfig, app: Quart) -> QuartSQLAlchemy:
    """
    This pytest fixture should return the QuartSQLAlchemy object
    """
    return QuartSQLAlchemy(db_config, app)


@pytest.fixture(scope="session", autouse=True)
@pytest.fixture
def database_test_fixtures(_db: QuartSQLAlchemy) -> t.Generator[None, None, None]:
    """
    This pytest fixture should use the injected session to load any necessary testing fixtures.
    """
    _db.create_all()

    with _db.bind.Session() as s:
        with s.begin():
            # add test fixtures to this session
            pass

    yield

    _db.drop_all()


@pytest.fixture(autouse=True)
def db_test_transaction(
    _db: QuartSQLAlchemy, database_test_fixtures: None
) -> t.Generator[TestTransaction, None, None]:
    """
    This pytest fixture should yield a synchronous TestTransaction
    """
    with _db.bind.test_transaction(savepoint=True) as test_transaction:
        yield test_transaction


@pytest.fixture(autouse=True)
async def async_db_test_transaction(
    _db: QuartSQLAlchemy, database_test_fixtures: None
) -> t.AsyncGenerator[TestTransaction, None]:
    """
    This pytest fixture should yield an asynchronous TestTransaction
    """
    async_bind: AsyncBind = _db.get_bind("async")  # type: ignore
    async with async_bind.test_transaction(savepoint=True) as async_test_transaction:
        yield async_test_transaction


@pytest.fixture(autouse=True)
def patch_sessionmakers(
    _db: QuartSQLAlchemy,
    db_test_transaction: TestTransaction,
    async_db_test_transaction: AsyncTestTransaction,
    monkeypatch,
) -> t.Generator[None, None, None]:
    for bind in _db.binds.values():
        if isinstance(bind, AsyncBind):
            savepoint_bound_session = async_db_test_transaction.Session
        else:
            savepoint_bound_session = db_test_transaction.Session

        monkeypatch.setattr(bind, "Session", savepoint_bound_session)

    yield


@pytest.fixture(name="db", autouse=True)
def patched_db(_db, patch_sessionmakers):
    return _db
