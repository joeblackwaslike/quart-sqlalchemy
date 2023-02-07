from __future__ import annotations

import asyncio
import typing as t
from copy import deepcopy

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.model import Model
from tests import constants


sa = sqlalchemy

Base = sa.orm.declarative_base()


# class Base(Model):
#     pass


# class Todo(Model):
#     # __tablename__ = "todo"
#     id = sa.Column(sa.Integer, primary_key=True)
#     title = sa.Column(sa.String)


@pytest.fixture(name="app_config", scope="module")
def _app_config_fixture():
    return deepcopy(constants.simple_config)


@pytest.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app(request: pytest.FixtureRequest, app_config) -> Quart:
    app = Quart(request.module.__name__)
    app.config.from_mapping(app_config)
    return app


@pytest.fixture
async def db(app: Quart) -> t.AsyncGenerator[SQLAlchemy, None]:
    yield SQLAlchemy(app)


@pytest.fixture(name="Todo")
async def _todo_fixture(app: Quart, db: SQLAlchemy) -> t.AsyncGenerator[Model, None]:
    class Todo(db.Model):
        # __tablename__ = "todo"
        id = sa.Column(sa.Integer, primary_key=True)
        title = sa.Column(sa.String)

    async with app.app_context():
        db.create_all()

    yield Todo

    async with app.app_context():
        db.drop_all()
