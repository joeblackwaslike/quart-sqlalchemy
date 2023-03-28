import pytest
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
from quart import Quart

from quart_sqlalchemy.framework import QuartSQLAlchemy

from ...base import SimpleTestBase


sa = sqlalchemy


class TestQuartSQLAlchemy(SimpleTestBase):
    def test_init_app(self, db: QuartSQLAlchemy, app: Quart):
        assert app.extensions["sqlalchemy"] == db

    def test_init_app_raises_runtime_error_when_already_initialized(self, db: QuartSQLAlchemy):
        app = Quart(__name__)
        db.init_app(app)
        with pytest.raises(RuntimeError):
            db.init_app(app)
