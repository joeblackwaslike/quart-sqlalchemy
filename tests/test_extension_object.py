from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped
from werkzeug.exceptions import NotFound

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.record_queries import get_recorded_queries


sa = sqlalchemy


async def test_get_or_404(app: Quart, db: SQLAlchemy, Todo: t.Any) -> None:
    async with app.app_context():
        item = Todo()
        db.session.add(item)
        db.session.commit()

        assert db.session.get_or_404(Todo, 1) is item

        with pytest.raises(NotFound):
            db.session.get_or_404(Todo, 2)


async def test_get_or_404_kwargs(app: Quart) -> None:
    app.config["SQLALCHEMY_RECORD_QUERIES"] = True
    db = SQLAlchemy(app)

    class User(db.Model):
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)

    class Todo(db.Model):
        id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
        user_id: Mapped[int] = sa.orm.mapped_column(sa.ForeignKey(User.id))
        user = sa.orm.relationship(User)

    async with app.app_context():
        db.create_all()
        db.session.add(Todo(user=User()))
        db.session.commit()

    async with app.app_context():
        item = db.session.get_or_404(Todo, 1, options=[db.joinedload(Todo.user)])
        assert item.user.id == 1
        # one query with join, no second query when accessing relationship
        assert len(get_recorded_queries()) == 1


async def test_paginate(app: Quart, db: SQLAlchemy, Todo: t.Any) -> None:
    total = 10
    per_page = 2
    page = 1

    async with app.app_context():
        todos = [Todo() for _ in range(total)]
        db.session.add_all(todos)
        db.session.commit()

        pager = db.session.paginate(db.select(Todo), page=page, per_page=per_page)

        assert pager.total == total
        assert pager.per_page == per_page
        assert pager.page == page
        assert pager.pages == total // per_page
        assert len(pager.items) == per_page

        next_page = pager.next()
        assert next_page.page == 2
        assert len(pager.items) == per_page

        pager = db.session.paginate(db.select(Todo), page=page, per_page=per_page)
        page_items = list(pager)
        assert len(page_items) == per_page


async def test_test_transaction(app: Quart, db: SQLAlchemy, Todo: t.Any):
    async with app.app_context():
        with db.test_transaction():
            assert db.session.execute(sa.text("select count(*) from todo;")).scalar() == 0

            db.session.add(Todo())
            db.session.commit()
            assert db.session.execute(sa.text("select count(*) from todo;")).scalar() == 1

        with db.test_transaction():
            assert db.session.execute(sa.text("select count(*) from todo;")).scalar() == 0
