from __future__ import annotations

import pytest
import sqlalchemy as sa
from quart import Quart

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.session import Session


async def test_scope(app: Quart, db: SQLAlchemy) -> None:
    with pytest.raises(RuntimeError):
        db.session()

    async with app.app_context():
        first = db.session()
        second = db.session()
        assert first is second
        assert isinstance(first, Session)

    async with app.app_context():
        third = db.session()
        assert first is not third


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
    
    async with app.app_context():
        db = SQLAlchemy(app, session_options={"class_": CustomSession})
        assert isinstance(db.session(), CustomSession)


async def test_session_uses_bind_key(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
        db = SQLAlchemy(app)

        class User(db.Model):
            id = sa.Column(sa.Integer, primary_key=True)

        class Post(db.Model):
            __bind_key__ = "a"
            id = sa.Column(sa.Integer, primary_key=True)

        assert db.session.get_bind(mapper=User) is db.engine
        assert db.session.get_bind(mapper=Post) is db.engines["a"]
