from __future__ import annotations

import random
import typing as t
from copy import deepcopy
from datetime import datetime

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import Base
from quart_sqlalchemy.framework import QuartSQLAlchemy
from quart_sqlalchemy.model.mixins import ComparableMixin
from quart_sqlalchemy.model.mixins import DynamicArgsMixin
from quart_sqlalchemy.model.mixins import EagerDefaultsMixin
from quart_sqlalchemy.model.mixins import TableNameMixin

from . import constants


sa = sqlalchemy


class SimpleTestBase:
    @pytest.fixture(scope="class")
    def Base(self) -> t.Type[t.Any]:
        return Base

    @pytest.fixture(scope="class")
    def app_config(self, Base):
        config = deepcopy(constants.simple_config)
        config.update(SQLALCHEMY_BASE_CLASS=Base)
        return config

    @pytest.fixture(scope="class")
    def app(self, app_config, request):
        app = Quart(request.module.__name__)
        app.config.from_mapping(app_config)
        app.config["TESTING"] = True
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart) -> t.Generator[QuartSQLAlchemy, None, None]:
        db = QuartSQLAlchemy(app=app)

        yield db

    @pytest.fixture(scope="class")
    def models(
        self, app: Quart, db: QuartSQLAlchemy
    ) -> t.Generator[t.Mapping[str, t.Type[t.Any]], None, None]:
        class Todo(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional["User"]] = sa.orm.relationship(
                back_populates="todos", lazy="noload", uselist=False
            )

        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(
                primary_key=True,
                autoincrement=True,
            )
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

            todos: Mapped[t.List[Todo]] = sa.orm.relationship(lazy="noload", back_populates="user")

        yield dict(todo=Todo, user=User)
        # We need to cleanup these objects that like to retain state beyond the fixture scope lifecycle
        Base.registry.dispose()
        Base.metadata.clear()

    @pytest.fixture(scope="class", autouse=True)
    def create_drop_all(self, db: QuartSQLAlchemy, models):
        db.create_all()
        yield
        db.drop_all()

    @pytest.fixture(scope="class")
    def Todo(self, models: t.Mapping[str, t.Type[t.Any]]) -> t.Type[sa.orm.DeclarativeBase]:
        return models["todo"]

    @pytest.fixture(scope="class")
    def User(self, models: t.Mapping[str, t.Type[t.Any]]) -> t.Type[sa.orm.DeclarativeBase]:
        return models["user"]

    @pytest.fixture(scope="class")
    def _user_fixtures(self, User: t.Type[t.Any], Todo: t.Type[t.Any]):
        users = []
        for i in range(5):
            user = User(name=f"user: {i}")
            for j in range(random.randint(0, 6)):
                todo = Todo(title=f"todo: {j}")
                user.todos.append(todo)
            users.append(user)
        return users

    @pytest.fixture(scope="class")
    def _add_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _user_fixtures
    ) -> None:
        with db.bind.Session() as s:
            with s.begin():
                s.add_all(_user_fixtures)

    @pytest.fixture(scope="class", autouse=True)
    def db_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _add_fixtures
    ) -> t.Dict[t.Type[t.Any], t.Sequence[t.Any]]:
        with db.bind.Session() as s:
            users = s.scalars(sa.select(User).options(sa.orm.selectinload(User.todos))).all()
            todos = s.scalars(sa.select(Todo).options(sa.orm.selectinload(Todo.user))).all()

        return {User: users, Todo: todos}


class MixinTestBase:
    default_mixins = (
        DynamicArgsMixin,
        EagerDefaultsMixin,
        TableNameMixin,
        ComparableMixin,
    )
    extra_mixins = ()

    @pytest.fixture(scope="class")
    def Base(self) -> t.Type[t.Any]:
        return type(
            "Base",
            tuple(self.extra_mixins + self.default_mixins),
            {"__abstract__": True},
        )

    @pytest.fixture(scope="class")
    def app_config(self, Base):
        config = deepcopy(constants.simple_config)
        config.update(SQLALCHEMY_BASE_CLASS=Base)
        return config

    @pytest.fixture(scope="class")
    def app(self, app_config, request):
        app = Quart(request.module.__name__)
        app.config.from_mapping(app_config)
        app.config["TESTING"] = True
        return app

    @pytest.fixture(scope="class")
    def db(self, app: Quart) -> t.Generator[QuartSQLAlchemy, None, None]:
        db = QuartSQLAlchemy(app=app)

        yield db

        # It's very important to clear the class _instances dict before recreating binds with the same name.
        # Bind._instances.clear()

    @pytest.fixture(scope="class")
    def models(
        self, app: Quart, db: QuartSQLAlchemy
    ) -> t.Generator[t.Mapping[str, t.Type[t.Any]], None, None]:
        class Todo(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional["User"]] = sa.orm.relationship(
                back_populates="todos", lazy="noload", uselist=False
            )

        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(
                primary_key=True,
                autoincrement=True,
            )
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

            todos: Mapped[t.List[Todo]] = sa.orm.relationship(lazy="noload", back_populates="user")

        yield dict(todo=Todo, user=User)
        # We need to cleanup these objects that like to retain state beyond the fixture scope lifecycle
        Base.registry.dispose()
        Base.metadata.clear()

    @pytest.fixture(scope="class", autouse=True)
    def create_drop_all(self, db: QuartSQLAlchemy, models):
        db.create_all()
        yield
        db.drop_all()

    @pytest.fixture(scope="class")
    def Todo(self, models: t.Mapping[str, t.Type[t.Any]]) -> t.Type[sa.orm.DeclarativeBase]:
        return models["todo"]

    @pytest.fixture(scope="class")
    def User(self, models: t.Mapping[str, t.Type[t.Any]]) -> t.Type[sa.orm.DeclarativeBase]:
        return models["user"]

    @pytest.fixture(scope="class")
    def _user_fixtures(self, User: t.Type[t.Any], Todo: t.Type[t.Any]):
        users = []
        for i in range(5):
            user = User(name=f"user: {i}")
            for j in range(random.randint(0, 6)):
                todo = Todo(title=f"todo: {j}")
                user.todos.append(todo)
            users.append(user)
        return users

    @pytest.fixture(scope="class")
    def _add_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _user_fixtures
    ) -> None:
        with db.bind.Session() as s:
            with s.begin():
                s.add_all(_user_fixtures)

    @pytest.fixture(scope="class", autouse=True)
    def db_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _add_fixtures
    ) -> t.Dict[t.Type[t.Any], t.Sequence[t.Any]]:
        with db.bind.Session() as s:
            users = s.scalars(sa.select(User).options(sa.orm.selectinload(User.todos))).all()
            todos = s.scalars(sa.select(Todo).options(sa.orm.selectinload(Todo.user))).all()

        return {User: users, Todo: todos}


class AsyncTestBase(SimpleTestBase):
    @pytest.fixture(scope="class")
    def app_config(self, Base):
        config = deepcopy(constants.async_config)
        config.update(SQLALCHEMY_BASE_CLASS=Base)
        return config

    @pytest.fixture(scope="class", autouse=True)
    async def create_drop_all(self, db: QuartSQLAlchemy, models) -> t.AsyncGenerator[None, None]:
        await db.create_all()
        yield
        await db.drop_all()

    @pytest.fixture(scope="class")
    async def _add_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _user_fixtures
    ) -> None:
        async with db.bind.Session() as s:
            async with s.begin():
                s.add_all(_user_fixtures)

    @pytest.fixture(scope="class", autouse=True)
    async def db_fixtures(
        self, db: QuartSQLAlchemy, User: t.Type[t.Any], Todo: t.Type[t.Any], _add_fixtures
    ) -> t.Dict[t.Type[t.Any], t.Sequence[t.Any]]:
        async with db.bind.Session() as s:
            users = (
                await s.scalars(sa.select(User).options(sa.orm.selectinload(User.todos)))
            ).all()
            todos = (await s.scalars(sa.select(Todo).options(sa.orm.selectinload(Todo.user)))).all()

        return {User: users, Todo: todos}


class ComplexTestBase(SimpleTestBase):
    @pytest.fixture(scope="class")
    def app_config(self, Base):
        config = deepcopy(constants.complex_config)
        config.update(SQLALCHEMY_BASE_CLASS=Base)
        return config


# class CustomMixinTestBase(SimpleTestBase):
#     default_mixins = (
#         DynamicArgsMixin,
#         EagerDefaultsMixin,
#         TableNameMixin,
#     )
#     additional_mixins = ()

#     @pytest.fixture(scope="class")
#     def Base(self) -> t.Type[t.Any]:
#         return type(
#             "Base",
#             tuple(self.additional_mixins + self.default_mixins),
#             {"__abstract__": True},
#         )

#     @pytest.fixture(scope="class")
#     def app_config(self, Base):
#         config = deepcopy(constants.simple_config)
#         config["SQLALCHEMY_BASE_CLASS"] = Base
#         config["TESTING"] = True
#         return config
