from __future__ import annotations

import os.path
import unittest.mock

import pytest
import sqlalchemy as sa
from quart import Quart

from quart_sqlalchemy import SQLAlchemy


async def test_default_engine(app: Quart, db: SQLAlchemy) -> None:
    async with app.app_context():
        assert db.engine is db.engines[None]

    with pytest.raises(RuntimeError):
        assert db.engine


async def test_engine_per_bind(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
        db = SQLAlchemy(app)
        assert db.engines["a"] is not db.engine


async def test_config_engine_options(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"echo": True}
        db = SQLAlchemy(app)
        assert db.engine.echo


async def test_init_engine_options(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"echo": False}
        app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
        db = SQLAlchemy(app, engine_options={"echo": True})
        # init is default
        assert db.engines["a"].echo
        # config overrides init
        assert not db.engine.echo


async def test_config_echo(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_ECHO"] = True
        db = SQLAlchemy(app)
        assert db.engine.echo
        assert db.engine.pool.echo


@pytest.mark.parametrize(
    "value",
    [
        "sqlite://",
        sa.engine.URL.create("sqlite"),
        {"url": "sqlite://"},
        {"url": sa.engine.URL.create("sqlite")},
    ],
)
async def test_url_type(app: Quart, value: str | sa.engine.URL) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_BINDS"] = {"a": value}
        db = SQLAlchemy(app)
        assert str(db.engines["a"].url) == "sqlite://"


def test_no_binds_error(app: Quart) -> None:
    del app.config["SQLALCHEMY_DATABASE_URI"]

    with pytest.raises(RuntimeError) as info:
        SQLAlchemy(app)

    e = "Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set."
    assert str(info.value) == e


async def test_no_default_url(app: Quart) -> None:
    async with app.app_context():
        del app.config["SQLALCHEMY_DATABASE_URI"]
        app.config["SQLALCHEMY_BINDS"] = {"a": "sqlite://"}
        db = SQLAlchemy(app, engine_options={"echo": True})
        assert None not in db.engines
        assert "a" in db.engines


async def test_sqlite_relative_path(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
        db = SQLAlchemy(app)
        db.create_all()
        assert not isinstance(db.engine.pool, sa.pool.StaticPool)
        db_path = db.engine.url.database
        assert db_path.startswith(str(app.instance_path))  # type: ignore[union-attr]
        assert os.path.exists(db_path)  # type: ignore[arg-type]


async def test_sqlite_driver_level_uri(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///file:test.db?uri=true"
        db = SQLAlchemy(app)
        db.create_all()
        db_path = db.engine.url.database
        assert db_path is not None
        assert db_path.startswith(f"file:{app.instance_path}")
        assert os.path.exists(db_path[5:])


async def test_sqlite_memory_defaults(app: Quart) -> None:
    with unittest.mock.patch.object(SQLAlchemy, "_make_engine", autospec=True) as make_engine:
        SQLAlchemy(app)
        options = make_engine.call_args[0][2]
        assert options["poolclass"] is sa.pool.StaticPool
        assert options["connect_args"]["check_same_thread"] is False


async def test_mysql_defaults(app: Quart) -> None:
    with unittest.mock.patch.object(SQLAlchemy, "_make_engine", autospec=True) as make_engine:
        app.config["SQLALCHEMY_DATABASE_URI"] = "mysql:///test"
        SQLAlchemy(app)
        options = make_engine.call_args[0][2]
        assert options["pool_recycle"] == 7200
        assert options["url"].query["charset"] == "utf8mb4"
