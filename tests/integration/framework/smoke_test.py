import typing as t

import pytest
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util

from quart_sqlalchemy.framework import QuartSQLAlchemy

from ...base import SimpleTestBase


sa = sqlalchemy


class TestQuartSQLAlchemySmoke(SimpleTestBase):
    def test_simple_transactional_orm_flow(self, db: QuartSQLAlchemy, Todo: t.Any):
        with db.bind.Session() as s:
            with s.begin():
                todo = Todo()
                s.add(todo)
                s.flush()
                s.refresh(todo)

        with db.bind.Session() as s:
            with s.begin():
                select_todo = s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()
                assert todo == select_todo

                s.delete(select_todo)

        with db.bind.Session() as s:
            with pytest.raises(sa.exc.NoResultFound):
                s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()

    def test_simple_transactional_core_flow(self, db: QuartSQLAlchemy, Todo: t.Any):
        with db.bind.engine.connect() as conn:
            with conn.begin():
                result = conn.execute(sa.insert(Todo))
                insert_row = result.inserted_primary_key

            select_row = conn.execute(sa.select(Todo).where(Todo.id == insert_row.id)).one()
            assert select_row.id == insert_row.id

        with db.bind.engine.connect() as conn:
            with conn.begin():
                result = conn.execute(sa.delete(Todo).where(Todo.id == select_row.id))

        assert result.rowcount == 1
        assert result.lastrowid == select_row.id

        with db.bind.engine.connect() as conn:
            with pytest.raises(sa.exc.NoResultFound):
                conn.execute(sa.select(Todo).where(Todo.id == insert_row.id)).one()

    def test_orm_models_comparable(self, db: QuartSQLAlchemy, Todo: t.Any):
        with db.bind.Session() as s:
            with s.begin():
                todo = Todo()
                s.add(todo)
                s.flush()
                s.refresh(todo)

        with db.bind.Session() as s:
            select_todo = s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()
            assert todo == select_todo
