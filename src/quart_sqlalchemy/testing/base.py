from __future__ import annotations

import asyncio
import typing as t
from contextlib import asynccontextmanager
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
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


def create_todo_model(db):
    class Todo(db.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        name = sa.Column(sa.String(50), default="default")

    return Todo


class SQLAlchemyBase:
    @contextmanager
    def sync_app_context(self, app: Quart):
        ctx = AppContext(app)
        reset_token = _cv_app.set(ctx)

        try:
            yield ctx
        finally:
            _cv_app.reset(reset_token)

    @pytest.fixture(scope="class")
    def event_loop(self):
        policy = asyncio.get_event_loop_policy()
        loop = policy.new_event_loop()
        yield loop
        loop.close()

    @pytest.fixture(scope="class")
    def app_config(self) -> dict[str, t.Any]:
        return deepcopy(simple_config)

    @pytest.fixture(scope="class")
    def app(self, app_config) -> Quart:
        app = Quart(__name__)
        app.config.from_mapping(app_config)
        return app

    @pytest.fixture(scope="class")
    async def db(self, app: Quart) -> SQLAlchemy:
        return SQLAlchemy(app)

    @pytest.fixture(scope="class", autouse=True)
    async def Todo(self, app: Quart, db: SQLAlchemy):
        Todo = create_todo_model(db)

        async with app.app_context():
            db.create_all()

        yield Todo

        async with app.app_context():
            db.drop_all()

    def assert_session_invariant(self, connection: sa.Connection) -> None:
        assert connection.exec_driver_sql("select count(*) from todo").scalar() == 0

    @pytest.fixture
    def db_engine(self, app: Quart, db: SQLAlchemy) -> sa.Engine:
        return t.cast(sa.Engine, db.get_bind(None, app=app))

    @pytest.fixture(autouse=True)
    def db_scoped_session(
        self, app: Quart, db: SQLAlchemy, db_engine: sa.Engine
    ) -> t.Generator[sa.orm.scoped_session, None, None]:
        with db_engine.connect() as connection:
            with connection.begin() as transaction:
                sessionmaker_options = dict(
                    **db._session_options,
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                    scopefunc=partial(db.get_session_scope, cache_fallback_enabled=True),
                )

                Session = db._make_scoped_session(sessionmaker_options)

                connection.begin_nested()

                try:
                    yield Session
                finally:
                    transaction.rollback()

            self.assert_session_invariant(connection)
        Session.remove()

    @pytest.fixture(autouse=True)
    def db_session(
        self, db_scoped_session: sa.orm.scoped_session
    ) -> t.Generator[sa.orm.Session, None, None]:
        with db_scoped_session() as session:
            try:
                yield session
            except Exception:
                session.rollback()
                raise

    @pytest.fixture(autouse=True)
    def db_mocked(
        self,
        db: SQLAlchemy,
        db_scoped_session: sa.orm.scoped_session,
        db_session: sa.orm.Session,
        mocker,
    ) -> t.Generator[SQLAlchemy, None, None]:
        mocker.patch.object(db, "_make_scoped_session", return_value=db_session)
        mocker.patch.object(db, "session", new=db_scoped_session)
        yield db
