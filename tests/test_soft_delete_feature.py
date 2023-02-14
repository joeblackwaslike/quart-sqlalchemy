from __future__ import annotations

import pdb
import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.mixins import SoftDeleteMixin
from quart_sqlalchemy.model import Model

from .base import SimpleTestBase


sa = sqlalchemy


class TestSoftDeleteFeature(SimpleTestBase):
    @pytest.fixture
    async def Todo(self, app: Quart, db: SQLAlchemy) -> t.AsyncGenerator[Model, None]:
        class Todo(SoftDeleteMixin, db.Model):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            title: Mapped[str] = sa.orm.mapped_column()

        async with app.app_context():
            db.create_all()

        yield Todo

        async with app.app_context():
            db.drop_all()

    async def test_inactive_filtered(self, app: Quart, db: SQLAlchemy, Todo):
        async with app.app_context():
            todo = Todo(title="todo")
            db.session.add(todo)
            db.session.commit()
            db.session.refresh(todo)

            result = db.session.get(Todo, todo.id)
            assert result.id == todo.id
            assert result.is_active is True

            result.is_active = False

            db.session.add(result)
            db.session.commit()
            db.session.refresh(result)

            todos = db.session.scalars(sa.select(Todo)).all()
            assert len(todos) == 0

            todos = db.session.scalars(
                sa.select(Todo).execution_options(include_inactive=True)
            ).all()
            assert len(todos) == 1

            result = db.session.get(Todo, todo.id, execution_options=dict(include_inactive=True))
            assert result.id == todo.id
            assert result.is_active is False
