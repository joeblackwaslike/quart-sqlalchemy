from __future__ import annotations

import typing as t
from pathlib import Path

import pytest

import sqlalchemy as sa
from quart import  Quart
from quart.ctx import AppContext


from quart_sqlalchemy import SQLAlchemy


@pytest.fixture
def app(request, tmp_path):
    app = Quart(request.module.__name__, instance_path=str(tmp_path / "instance"))
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["SQLALCHEMY_RECORD_QUERIES"] = False
    return app


@pytest.fixture
async def app_ctx(app: Quart) -> t.Generator[AppContext, None, None]:
    async with app.app_context() as ctx:
        yield ctx


@pytest.fixture
def db(app: Quart) -> SQLAlchemy:
    return SQLAlchemy(app)


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
