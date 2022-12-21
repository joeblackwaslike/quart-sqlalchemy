from __future__ import annotations

import asyncio
import typing as t
from pathlib import Path

import pytest
import sqlalchemy as sa
from quart import Quart

from quart_sqlalchemy import SQLAlchemy


@pytest.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app(request: pytest.FixtureRequest, tmp_path: Path) -> Quart:
    app = Quart(request.module.__name__, instance_path=str(tmp_path / "instance"))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_RECORD_QUERIES"] = False
    return app


@pytest.fixture
async def db(app: Quart) -> SQLAlchemy:
    yield SQLAlchemy(app)


@pytest.fixture
async def Todo(app: Quart, db: SQLAlchemy) -> t.Any:
    class Todo(db.Model):
        id = sa.Column(sa.Integer, primary_key=True)
        title = sa.Column(sa.String)

    async with app.app_context():
        db.create_all()

    yield Todo

    async with app.app_context():
        db.drop_all()
