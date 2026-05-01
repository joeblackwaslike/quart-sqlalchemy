import random
import typing as t
from datetime import datetime

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy

from . import constants

sa = sqlalchemy


class SimpleTestBase:
    @pytest.fixture(scope="class")
    def app(self, request):
        app = Quart(request.module.__name__)
        app.config.from_mapping({"TESTING": True})
        return app

    @pytest.fixture(scope="class")
    def sqlalchemy_config(self):
        return SQLAlchemyConfig(**constants.simple_mapping_config)

    @pytest.fixture(scope="class")
    def db(self, sqlalchemy_config, app: Quart) -> QuartSQLAlchemy:
        return QuartSQLAlchemy(sqlalchemy_config, app)
        # yield db
        # db.drop_all()

    @pytest.fixture(scope="class")
    def models(self, app: Quart, db: QuartSQLAlchemy) -> t.Mapping[str, type[t.Any]]:
        class Todo(db.Base):
            __tablename__ = "todo"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[int | None] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped["User | None"] = sa.orm.relationship(back_populates="todos", lazy="noload")

        class User(db.Base):
            __tablename__ = "user"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="default")
            created_at: Mapped[datetime] = sa.orm.mapped_column(
                default=sa.func.now(),
                server_default=sa.FetchedValue(),
            )
            time_updated: Mapped[datetime] = sa.orm.mapped_column(
                default=sa.func.now(),
                onupdate=sa.func.now(),
                server_default=sa.FetchedValue(),
                server_onupdate=sa.FetchedValue(),
            )

            todos: Mapped[list[Todo]] = sa.orm.relationship(lazy="noload", back_populates="user")

        return dict(todo=Todo, user=User)

    @pytest.fixture(scope="class", autouse=True)
    def create_drop_all(self, db: QuartSQLAlchemy, models):
        db.create_all()
        yield
        db.drop_all()

    @pytest.fixture(scope="class")
    def Todo(self, models: t.Mapping[str, type[t.Any]]) -> type[sa.orm.DeclarativeBase]:
        return models["todo"]

    @pytest.fixture(scope="class")
    def User(self, models: t.Mapping[str, type[t.Any]]) -> type[sa.orm.DeclarativeBase]:
        return models["user"]

    @pytest.fixture(scope="class")
    def _user_fixtures(self, User: type[t.Any], Todo: type[t.Any]):
        users = []
        rng = random.Random(42)  # Fixed seed for reproducibility
        for i in range(5):
            user = User(name=f"user: {i}")
            for j in range(rng.randint(0, 6)):
                todo = Todo(title=f"todo: {j}")
                user.todos.append(todo)
            users.append(user)
        return users

    @pytest.fixture(scope="class")
    def _add_fixtures(self, db: QuartSQLAlchemy, User: type[t.Any], _user_fixtures) -> None:
        with db.bind.Session() as s:
            with s.begin():
                s.add_all(_user_fixtures)

    @pytest.fixture(scope="class", autouse=True)
    def db_fixtures(
        self, db: QuartSQLAlchemy, User: type[t.Any], Todo: type[t.Any], _add_fixtures
    ) -> dict[type[t.Any], t.Sequence[t.Any]]:
        with db.bind.Session() as s:
            users = s.scalars(sa.select(User).options(sa.orm.selectinload(User.todos))).all()
            todos = s.scalars(sa.select(Todo).options(sa.orm.selectinload(Todo.user))).all()

        return {User: users, Todo: todos}


class AsyncTestBase(SimpleTestBase):
    @pytest.fixture(scope="class")
    def sqlalchemy_config(self):
        return SQLAlchemyConfig(**constants.async_mapping_config)

    @pytest.fixture(scope="class", autouse=True)
    async def create_drop_all(self, db: QuartSQLAlchemy, models) -> t.AsyncGenerator[None, None]:
        await db.create_all()
        yield
        await db.drop_all()

    @pytest.fixture(scope="class")
    async def _add_fixtures(
        self, db: QuartSQLAlchemy, User: type[t.Any], Todo: type[t.Any], _user_fixtures
    ) -> None:
        async with db.bind.Session() as s:
            async with s.begin():
                s.add_all(_user_fixtures)

    @pytest.fixture(scope="class", autouse=True)
    async def db_fixtures(
        self, db: QuartSQLAlchemy, User: type[t.Any], Todo: type[t.Any], _add_fixtures
    ) -> dict[type[t.Any], t.Sequence[t.Any]]:
        async with db.bind.Session() as s:
            users = (
                await s.scalars(sa.select(User).options(sa.orm.selectinload(User.todos)))
            ).all()
            todos = (await s.scalars(sa.select(Todo).options(sa.orm.selectinload(Todo.user)))).all()

        return {User: users, Todo: todos}


class ComplexTestBase(SimpleTestBase):
    @pytest.fixture(scope="class")
    def sqlalchemy_config(self):
        return SQLAlchemyConfig(**constants.complex_mapping_config)
