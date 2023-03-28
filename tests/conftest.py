from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy

from . import constants


sa = sqlalchemy


@pytest.fixture(scope="session")
def app(request: pytest.FixtureRequest) -> Quart:
    app = Quart(request.module.__name__)
    app.config.from_mapping({"TESTING": True})
    return app


@pytest.fixture(scope="session")
def sqlalchemy_config():
    return SQLAlchemyConfig.parse_obj(constants.simple_mapping_config)


@pytest.fixture(scope="session")
def db(sqlalchemy_config, app: Quart) -> QuartSQLAlchemy:
    return QuartSQLAlchemy(sqlalchemy_config, app)


@pytest.fixture(name="Todo", scope="session")
def _todo_fixture(
    app: Quart, db: QuartSQLAlchemy
) -> t.Generator[t.Type[sa.orm.DeclarativeBase], None, None]:
    class Todo(db.Model):
        id: Mapped[int] = sa.orm.mapped_column(sa.Identity(), primary_key=True, autoincrement=True)
        title: Mapped[str] = sa.orm.mapped_column(default="default")

    db.create_all()

    yield Todo

    db.drop_all()
