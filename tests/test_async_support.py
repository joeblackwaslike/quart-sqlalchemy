from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart

from quart_sqlalchemy import SQLAlchemy

from .constants import async_config
from .constants import complex_config


sa = sqlalchemy


class TestSessionForAsyncDriver:
    @pytest.fixture(scope="class")
    def app(self, request: pytest.FixtureRequest) -> Quart:
        app = Quart(__name__)
        app.config.from_mapping(async_config)
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart) -> SQLAlchemy:
        return SQLAlchemy(app, is_async_session=True)

    @pytest.fixture(scope="class")
    async def Todo(self, app: Quart, db: SQLAlchemy) -> t.Any:
        class Todo(db.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String, default="default")

        async with app.app_context():
            await db.async_create_all(None)

        yield Todo

        async with app.app_context():
            await db.async_drop_all(None)

    @pytest.fixture(scope="class", autouse=True)
    async def todo_fixtures(self, app, db, Todo):
        async with app.app_context():
            todos = [Todo(title=f"todo: {i}") for i in range(10)]

            db.session.add_all(todos)
            await db.session.commit()

        return

    async def test_async_session(self, app, db, Todo):
        async with app.app_context():
            st = db.select(Todo)
            result = (await db.session.execute(st)).scalars().all()

        print(result)
        assert len(result) == 10


class TestRoutingSessionForAsyncBind:
    @pytest.fixture(scope="class")
    def app(self, request: pytest.FixtureRequest) -> Quart:
        app = Quart(__name__)
        app.config.from_mapping(complex_config)
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart) -> SQLAlchemy:
        return SQLAlchemy(app)

    @pytest.fixture(scope="class")
    async def Todo(self, app: Quart, db: SQLAlchemy) -> t.Any:
        class Todo(db.Model):
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String, default="default")

        async with app.app_context():
            db.create_all(None)

        yield Todo

        async with app.app_context():
            db.drop_all(None)

    @pytest.fixture(scope="class", autouse=True)
    async def todo_fixtures(self, app, db, Todo):
        async with app.app_context():
            todos = [Todo(title=f"todo: {i}") for i in range(10)]

            db.session.add_all(todos)
            db.session.commit()

        return

    @pytest.mark.xfail(reason="likely will never work in this context.")
    async def test_session_using_bind_async(self, app, db, Todo):
        async with app.app_context():
            st = db.select(Todo)
            async_session = db.session.using_bind("async")
            with async_session:
                result = (await async_session.execute(st)).scalars().all()

        print(result)
        assert len(result) == 10
