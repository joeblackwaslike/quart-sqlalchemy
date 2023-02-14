from __future__ import annotations

import typing as t

import sqlalchemy
from quart import Quart
from sqlalchemy import select

from quart_sqlalchemy import SQLAlchemy

from .base import ComplexTestBase


sa = sqlalchemy


class TestBindContextReadReplica(ComplexTestBase):
    async def test_flush_behavior(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            todos = [Todo(title=f"todo: {i}") for i in range(2)]
            db.session.add_all(todos)
            db.session.flush()

            st = db.select(Todo)
            result = db.session.execute(st).scalars().all()
        print(result)
        assert len(result) == 12

    async def test_flush_behavior_rolled_back(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            with db.bind_context(None, app=app) as ctx:
                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()

        print(result)
        assert len(result) == 10

    async def test_context_read_replica(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            with db.bind_context("read-replica", app=app) as ctx:
                ctx.session.add(Todo())
                ctx.session.commit()

                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()
        print(result)
        assert len(result) == 11


class TestBindContextAsync(ComplexTestBase):
    async def test_context_async(self, app: Quart, db: SQLAlchemy, Todo: t.Any):
        async with app.app_context():
            async with db.bind_context("async", app=app) as ctx:
                todo = Todo()
                ctx.session.add(todo)
                await ctx.session.commit()
                st = select(Todo)
                result = (await ctx.session.execute(st)).scalars().all()

            print(result)
            assert len(result) == 11

            with db.bind_context(None, app=app) as ctx:
                st = select(Todo)
                result = ctx.session.execute(st).scalars().all()
            print(result)
            assert len(result) == 11
