from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.model import Model

from .constants import simple_config


sa = sqlalchemy


@pytest.fixture
def app(request: pytest.FixtureRequest) -> Quart:
    app = Quart(request.module.__name__)
    app.config.from_mapping(simple_config)
    return app


@pytest.fixture
async def db(app: Quart) -> t.AsyncGenerator[SQLAlchemy, None]:
    yield SQLAlchemy(app)


@pytest.fixture(name="Todo")
async def _todo_fixture(app: Quart, db: SQLAlchemy) -> t.AsyncGenerator[Model, None]:
    class Todo(db.Model):
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
        title: Mapped[str] = sa.orm.mapped_column(default="default")

    async with app.app_context():
        db.create_all()

    yield Todo

    async with app.app_context():
        db.drop_all()
