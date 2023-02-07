import asyncio
import typing as t
from contextlib import asynccontextmanager
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from functools import partial
from types import SimpleNamespace

import pytest
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from quart import Quart
from quart.ctx import AppContext
from quart.globals import _cv_app

from quart_sqlalchemy import SQLAlchemy


sa = sqlalchemy


simple_config = {
    "SQLALCHEMY_DATABASE_URI": "sqlite:///file:simple.db?mode=memory&cache=shared&uri=true",
    "SQLALCHEMY_ECHO": False,
    "SQLALCHEMY_ENGINE_OPTIONS": dict(
        connect_args=dict(
            check_same_thread=True,
        ),
    ),
}

async_config = {
    "SQLALCHEMY_DATABASE_URI": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
    "SQLALCHEMY_ECHO": False,
    "SQLALCHEMY_ENGINE_OPTIONS": dict(
        connect_args=dict(
            check_same_thread=True,
        ),
    ),
}

complex_config = {
    "SQLALCHEMY_BINDS": {
        None: dict(
            url="sqlite:///file:complex.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "read-replica": dict(
            url="sqlite:///file:complex.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "async": dict(
            url="sqlite+aiosqlite:///file:complex.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
    },
    "SQLALCHEMY_ECHO": False,
}

configs = [simple_config, async_config, complex_config]


@contextmanager
def sync_app_context(app):
    ctx = AppContext(app)
    reset_token = _cv_app.set(ctx)

    try:
        yield ctx
    finally:
        _cv_app.reset(reset_token)


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# @pytest.fixture(name="simple_config")
# def _simple_config():
#     return deepcopy(simple_config)


@pytest.fixture(name="async_config", scope="session")
def _async_config():
    return deepcopy(async_config)


@pytest.fixture(name="app_config", scope="session")
def _app_config():
    return deepcopy(simple_config)


@pytest.fixture(name="app", scope="session")
def _app(app_config):
    app = Quart(__name__)
    app.config.from_mapping(app_config)
    return app


@pytest.fixture(name="async_app", scope="session")
def _async_app(async_config):
    app = Quart(__name__)
    app.config.from_mapping(async_config)
    return app


@pytest.fixture(name="db", scope="session")
def _db(app: Quart) -> SQLAlchemy:
    return SQLAlchemy(app)


@pytest.fixture(name="async_db", scope="session")
def _async_db(async_app: Quart) -> SQLAlchemy:
    return SQLAlchemy(async_app)


@contextmanager
def ephemeral_session(
    db: SQLAlchemy,
    app: Quart,
    bind_key: t.Optional[str] = None,
) -> t.Generator[sa.orm.Session, None, None]:
    engine = t.cast(sa.Engine, db.get_bind(bind_key, app=app))
    with engine.connect() as connection:
        with connection.begin() as transaction:
            sessionmaker_options = dict(
                **db._session_options,
                bind=connection,
                join_transaction_mode="create_savepoint",
                scopefunc=partial(db.get_session_scope, cache_fallback_enabled=True),
            )

            Session = db._make_scoped_session(sessionmaker_options)
            connection.begin_nested()

            with Session() as session:
                try:
                    yield session
                except Exception:
                    session.rollback()
                    raise
                finally:
                    transaction.rollback()
        assert connection.exec_driver_sql("select count(*) from todo").scalar() == 0

    # Session.remove()


# sa.ext.asyncio.async_scoped_session


@asynccontextmanager
async def async_ephemeral_session(
    db: SQLAlchemy,
    bind_key: t.Optional[str] = None,
) -> t.AsyncGenerator[sa.ext.asyncio.AsyncSession, None]:
    engine = t.cast(sa.ext.asyncio.AsyncEngine, db.engines[bind_key])
    async with engine.connect() as connection:
        async with connection.begin() as transaction:
            sessionmaker_options = dict(
                **db._session_options,
                bind=connection,
                join_transaction_mode="create_savepoint",
                scopefunc=partial(db.get_session_scope, cache_fallback_enabled=True),
            )
            Session = t.cast(
                sa.ext.asyncio.async_scoped_session,
                db._make_scoped_session(sessionmaker_options, is_async=True),
            )
            await connection.begin_nested()

            async with Session() as session:
                try:
                    yield session
                except Exception:
                    await session.rollback()
                    raise
            await transaction.rollback()
        assert (await connection.exec_driver_sql("select count(*) from todo")).scalar() == 0

    # await Session.remove()


def create_todo_model(db):
    class Todo(db.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(50), default="default")

    return Todo


@pytest.fixture(name="Todo")
def _todo_model(db: SQLAlchemy) -> t.Type[sa.orm.DeclarativeMeta]:
    return create_todo_model(db)


@pytest.fixture(name="AsyncTodo")
def _async_todo_model(async_db: SQLAlchemy) -> t.Type[sa.orm.DeclarativeMeta]:
    return create_todo_model(async_db)


@pytest.fixture(name="app_context")
async def _app_context(app, db):
    async with app.app_context():
        db.create_all()

    # task_ = asyncio.current_task()
    # print("before", id(task_), task_)
    # async with app.app_context():
    yield
    # task_ = asyncio.current_task()
    # print("after", id(task_), task_)

    async with app.app_context():
        db.drop_all()


@pytest.fixture
async def app_db_session(app, db, app_context):
    async with app.app_context():
        with ephemeral_session(db, app, bind_key=None) as session:
            yield session


@pytest.fixture(scope="module", name="db_session")
def _db_session(app: Quart, db: SQLAlchemy, Todo: t.Any) -> t.AsyncGenerator[sa.orm.Session, None]:
    # async with app.app_context():
    with sync_app_context(app):
        db.create_all()

    # async with app.app_context():
    # with sync_app_context(app):
    with ephemeral_session(db, app, bind_key=None) as session:
        yield session

    # async with app.app_context():
    with sync_app_context(app):
        db.drop_all()


@pytest.fixture(name="async_db_session")
async def _async_db_session(
    async_app: Quart, async_db: SQLAlchemy, AsyncTodo: t.Any
) -> t.AsyncGenerator[sa.ext.asyncio.AsyncSession, None]:
    async with async_app.app_context():
        await async_db.async_create_all()

    async with async_app.app_context():
        async with async_ephemeral_session(async_db) as session:
            yield session

    async with async_app.app_context():
        await async_db.async_drop_all()
