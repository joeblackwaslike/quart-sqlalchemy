from __future__ import annotations

import sqlalchemy as sa
from quart import Quart

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.record_queries import get_recorded_queries


async def test_query_info(app: Quart) -> None:
    async with app.app_context():
        app.config["SQLALCHEMY_RECORD_QUERIES"] = True
        db = SQLAlchemy(app)

        class Example(db.Model):
            id = sa.Column(sa.Integer, primary_key=True)

        db.create_all()
        db.session.execute(sa.select(Example).filter(Example.id < 5)).scalars()
        info = get_recorded_queries()[-1]
        assert info.statement is not None
        assert "SELECT" in info.statement
        assert "FROM example" in info.statement
        assert info.parameters[0][0] == 5
        assert info.duration == info.end_time - info.start_time
        assert "tests/test_record_queries.py:" in info.location
        assert "(test_query_info)" in info.location
