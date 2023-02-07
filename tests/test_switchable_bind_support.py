from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
from quart import Quart
from sqlalchemy import select

from quart_sqlalchemy import SQLAlchemy

from .constants import complex_config


sa = sqlalchemy


class TestBindContextReadReplica:
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
            __tablename__ = "todo"
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String, default="default")

        async with app.app_context():
            db.create_all(None)
            # await db.async_create_all("async")

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

    async def test_fixtures_count(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            st = db.select(Todo)
            result = db.session.execute(st).scalars().all()

        print(result)
        assert len(result) == 10

    async def test_flush_behavior(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            todos = [Todo(title=f"todo: {i}") for i in range(2)]
            db.session.add_all(todos)
            db.session.flush()

            st = db.select(Todo)
            result = db.session.execute(st).scalars().all()
        print(result)
        assert len(result) == 12

    async def test_flush_behavior_rolled_back(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            with db.bind_context(None, app) as ctx:
                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()

        print(result)
        assert len(result) == 10

    async def test_context_read_replica(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            with db.bind_context("read-replica", app) as ctx:
                ctx.session.add(Todo())
                ctx.session.commit()

                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()
        print(result)
        assert len(result) == 11

    async def test_context_async(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            async with db.bind_context("async", app) as ctx:
                # async with ctx.session() as session:
                todo = Todo()
                ctx.session.add(todo)
                await ctx.session.commit()
                st = select(Todo)
                result = (await ctx.session.execute(st)).scalars().all()
            print(result)
            assert len(result) == 12

            with db.bind_context(None, app) as ctx:
                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()
            print(result)
            assert len(result) == 12


class TestRoutingSession:
    @pytest.fixture(scope="class")
    def app(self, request: pytest.FixtureRequest) -> Quart:
        app = Quart(__name__)
        app.config.from_mapping(complex_config)
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart) -> SQLAlchemy:
        return SQLAlchemy(app)

    @pytest.fixture(scope="class")
    async def Todo(self, app: Quart, db: SQLAlchemy):
        class Todo(db.Model):
            __tablename__ = "todo"
            id = sa.Column(sa.Integer, primary_key=True)
            title = sa.Column(sa.String, default="default")

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

    async def test_fixtures_count(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            st = db.select(Todo)
            result = db.session.execute(st).scalars().all()

        print(result)
        assert len(result) == 10

    async def test_session_using_bind_executes_on_read_replica_engine(
        self, app: Quart, db: SQLAlchemy, Todo: t.Any
    ):
        async with app.app_context():
            st = db.select(Todo)
            result = db.session.using_bind("read-replica").execute(st).scalars().all()

        print(result)
        assert len(result) == 10
