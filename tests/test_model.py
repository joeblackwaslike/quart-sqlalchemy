from __future__ import annotations

import typing as t

import pytest
import sqlalchemy as sa
import sqlalchemy.orm
from quart import Quart

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.model import DefaultMeta
from quart_sqlalchemy.model import Model


def test_default_model_class(db: SQLAlchemy) -> None:
    assert db.Model.query_class is db.Query
    assert db.Model.metadata is db.metadata
    assert issubclass(db.Model, Model)
    assert isinstance(db.Model, DefaultMeta)


def test_custom_model_class(app: Quart) -> None:
    class CustomModel(Model):
        pass

    db = SQLAlchemy(app, model_class=CustomModel)
    assert issubclass(db.Model, CustomModel)
    assert isinstance(db.Model, DefaultMeta)


@pytest.mark.parametrize("base", [Model, object])
async def test_custom_declarative_class(app: Quart, base: t.Any) -> None:
    class CustomMeta(DefaultMeta):
        pass

    async with app.app_context():
        CustomModel = sa.orm.declarative_base(cls=base, name="Model", metaclass=CustomMeta)
        db = SQLAlchemy(app, model_class=CustomModel)
        assert db.Model is CustomModel
        assert db.Model.query_class is db.Query
        assert "query" in db.Model.__dict__


async def test_model_repr(app: Quart, db: SQLAlchemy) -> None:
    class User(db.Model):
        id = sa.Column(sa.Integer, primary_key=True)

    async with app.app_context():
        db.create_all()
        user = User()
        assert repr(user) == f"<User (transient {id(user)})>"
        db.session.add(user)
        assert repr(user) == f"<User (pending {id(user)})>"
        db.session.flush()
        assert repr(user) == f"<User {user.id}>"
