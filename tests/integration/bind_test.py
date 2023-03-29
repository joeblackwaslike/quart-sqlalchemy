from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm

from quart_sqlalchemy import SQLAlchemy

from .. import base


sa = sqlalchemy


class TestAsyncBind(base.AsyncTestBase):
    async def test_async_transactional_orm_flow(self, db: SQLAlchemy, Todo: t.Type[t.Any]):
        async with db.bind.Session() as s:
            async with s.begin():
                todo = Todo(title="hello")
                s.add(todo)
                await s.flush()
                await s.refresh(todo)

        async with db.bind.Session() as s:
            async with s.begin():
                select_todo = (await s.scalars(sa.select(Todo).where(Todo.id == todo.id))).one()
                assert todo == select_todo


class TestBindContext(base.ComplexTestBase):
    def test_bind_context_execution_isolation_level(self, db: SQLAlchemy, Todo: t.Type[t.Any]):
        with db.bind.context(engine_execution_options=dict(isolation_level="SERIALIZABLE")) as ctx:
            engine_execution_options = ctx.engine.get_execution_options()
            assert engine_execution_options["isolation_level"] == "SERIALIZABLE"

            with ctx.Session() as s:
                with s.begin():
                    todo = Todo(title="hello")
                    s.add(todo)
                    s.flush()
                    s.refresh(todo)


class TestTestTransaction(base.ComplexTestBase):
    def test_test_transaction_for_orm(self, db: SQLAlchemy, Todo: t.Type[t.Any]):
        with db.bind.test_transaction(savepoint=True) as tx:
            with tx.Session() as s:
                todo = Todo(title="hello")
                s.add(todo)
                s.commit()
                s.refresh(todo)

            with tx.Session() as s:
                select_todo = s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()

            assert select_todo == todo

        with db.bind.Session() as s:
            with pytest.raises(sa.orm.exc.NoResultFound):
                s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()
