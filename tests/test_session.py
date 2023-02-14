from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.model import Model
from quart_sqlalchemy.session import RoutingSession
from quart_sqlalchemy.session import Session

from .base import ComplexTestBase


sa = sqlalchemy


async def test_scope(app: Quart, db: SQLAlchemy) -> None:
    with pytest.raises(RuntimeError):
        db.session()

    async with app.app_context():
        first = db.session()
        second = db.session()
        assert first is second
        assert isinstance(first, RoutingSession)

    async with app.app_context():
        third = db.session()
        assert first is not third


class TestSessionsAndTransactions:
    async def test_session_manual(
        self,
        app: Quart,
        db: SQLAlchemy,
        Todo: Model,
    ):
        async with app.app_context():
            todo = Todo()
            db.session.add(todo)
            db.session.commit()
            db.session.refresh(todo)

            result = db.session.get(Todo, todo.id)

            db.session.close()

            assert result is todo

    async def test_session_context_commit_and_query(
        self,
        app: Quart,
        db: SQLAlchemy,
        Todo: Model,
    ):
        async with app.app_context():
            with db.session() as session:
                todo = Todo()
                session.add(todo)
                session.commit()
                session.refresh(todo)

                result = session.get(Todo, todo.id)
            assert result is todo

    async def test_session_context_manager(
        self,
        app: Quart,
        db: SQLAlchemy,
        Todo: Model,
    ):
        async with app.app_context():
            with db.session() as session:
                with session.begin():
                    todo = Todo()
                    session.add(todo)

                # session.commit()
                # session.refresh(todo)
                result = session.get(Todo, todo.id)
            assert result is todo


async def test_custom_scope(app: Quart) -> None:
    count = 0

    def scope() -> int:
        nonlocal count
        count += 1
        return count

    db = SQLAlchemy(app, session_options={"scopefunc": scope})

    async with app.app_context():
        first = db.session()
        second = db.session()
        assert first is not second  # a new scope is generated on each call

        first.close()
        second.close()


async def test_session_class(app: Quart) -> None:
    class CustomSession(Session):
        pass

    db = SQLAlchemy(app, session_options={"class_": CustomSession})

    async with app.app_context():
        assert isinstance(db.session(), CustomSession)


async def test_session_uses_bind_key(app: Quart) -> None:
    app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
    db = SQLAlchemy(app)

    class User(db.Model):
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)

    class Post(db.Model):
        __bind_key__ = "a"
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)

    async with app.app_context():
        assert db.session.get_bind(mapper=User) is db.engine
        assert db.session.get_bind(mapper=Post) is db.engines["a"]


async def test_get_bind_inheritance(app: Quart) -> None:
    app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
    db = SQLAlchemy(app)

    class User(db.Model):
        __bind_key__ = "a"
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
        type: Mapped[str] = sa.orm.mapped_column(nullable=False)

        __mapper_args__ = {"polymorphic_on": type, "polymorphic_identity": "user"}

    class Admin(User):
        id: Mapped[int] = sa.orm.mapped_column(sa.ForeignKey(User.id), primary_key=True)
        org: Mapped[str] = sa.orm.mapped_column(nullable=False)

        __mapper_args__ = {"polymorphic_identity": "admin"}

    async with app.app_context():
        db.create_all()
        db.session.add(Admin(org="pallets"))
        db.session.commit()
        admin = db.session.execute(db.select(Admin)).scalar_one()
        db.session.expire(admin)

        assert admin.org == "pallets"


class TestRoutingSession(ComplexTestBase):
    async def test_session_using_bind_executes_on_read_replica_engine(
        self, app: Quart, db: SQLAlchemy, Todo: t.Any
    ):
        async with app.app_context():
            st = db.select(Todo)
            result = db.session.using_bind("read-replica").execute(st).scalars().all()

        print(result)
        assert len(result) == 10
