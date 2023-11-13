# This package is not finished

import typing as t
from contextlib import asynccontextmanager
from contextlib import contextmanager
from functools import partial

import pytest
import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from quart import Quart
from quart.ctx import AppContext
from quart.globals import _cv_app

from quart_sqlalchemy import SQLAlchemy


sa = sqlalchemy


@contextmanager
def sync_app_context(app):
    ctx = AppContext(app)
    reset_token = _cv_app.set(ctx)

    try:
        yield ctx
    finally:
        _cv_app.reset(reset_token)


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

    Session.remove()


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
        assert (
            await connection.exec_driver_sql("select count(*) from todo")
        ).scalar() == 0

    await Session.remove()


def create_todo_model(db):
    class Todo(db.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(50), default="default")

    return Todo


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
def _db_session(
    app: Quart, db: SQLAlchemy, Todo: t.Any
) -> t.AsyncGenerator[sa.orm.Session, None]:
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
