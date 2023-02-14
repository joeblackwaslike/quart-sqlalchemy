from __future__ import annotations

import pytest
import sqlalchemy
import sqlalchemy.orm

from .base import AsyncTestBase
from .base import ComplexTestBase


sa = sqlalchemy


class TestSessionForAsyncDriver(AsyncTestBase):
    async def test_async_session(self, app, db, Todo):
        async with app.app_context():
            st = db.select(Todo)
            result = (await db.session.execute(st)).scalars().all()

        print(result)
        assert len(result) == 10


class TestRoutingSessionForAsyncBind(ComplexTestBase):
    @pytest.mark.xfail(reason="likely will never work in this context.")
    async def test_session_using_bind_async(self, app, db, Todo):
        async with app.app_context():
            st = db.select(Todo)
            async_session = db.session.using_bind("async")
            with async_session:
                result = (await async_session.execute(st)).scalars().all()

        print(result)
        assert len(result) == 10
