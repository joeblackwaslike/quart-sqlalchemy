from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy

from .constants import async_config
from .constants import complex_config
from .constants import simple_config


sa = sqlalchemy


class SimpleTestBase:
    @pytest.fixture(scope="class")
    def app(self, request):
        app = Quart(request.module.__name__)
        app.config.from_mapping(simple_config)
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart):
        return SQLAlchemy(app)

    @pytest.fixture(scope="class")
    async def Todo(self, app: Quart, db: SQLAlchemy):
        class Todo(db.Model):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")

        async with app.app_context():
            db.create_all(None)

        yield Todo

        async with app.app_context():
            db.drop_all(None)


class AsyncTestBase:
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
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")

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


class ComplexTestBase:
    @pytest.fixture(scope="class")
    def app(self):
        app = Quart(__name__)
        app.config.from_mapping(complex_config)
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart):
        return SQLAlchemy(app)

    @pytest.fixture(scope="class")
    async def Todo(self, app: Quart, db: SQLAlchemy):
        class Todo(db.Model):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")

        async with app.app_context():
            db.create_all(None)

        yield Todo

        async with app.app_context():
            db.drop_all(None)

    @pytest.fixture(scope="class", autouse=True)
    async def todo_fixtures(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            todos = [Todo(title=f"todo: {i}") for i in range(10)]

            db.session.add_all(todos)
            db.session.commit()

            st = db.select(Todo)
            result = db.session.execute(st).scalars().all()
