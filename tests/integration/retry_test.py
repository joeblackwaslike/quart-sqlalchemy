from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm
import tenacity
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.retry import retry_config
from quart_sqlalchemy.retry import retrying_async_session
from quart_sqlalchemy.retry import retrying_session

from .. import base


sa = sqlalchemy


class TestRetryingSessions(base.ComplexTestBase):
    def test_retrying_session(self, db: SQLAlchemy, Todo: t.Type[t.Any], mocker):
        side_effects = [
            sa.exc.InvalidRequestError,
            sa.exc.InvalidRequestError,
            sa.exc.InvalidRequestError,
        ]

        session_add = mocker.Mock(
            side_effect=[
                sa.exc.InvalidRequestError,
                sa.exc.InvalidRequestError,
                sa.exc.InvalidRequestError,
            ]
        )

        # bind = db.get_bind("retry")

        # # conn_mock = mocker.patch.dict(bind.Session.kw, "bind")

        # with bind.Session() as s:
        #     todo = Todo(title="hello")
        #     s.add(todo)
        #     s.commit()

    def test_retrying_session_class(self, db: SQLAlchemy, Todo: t.Type[t.Any], mocker):
        class Unique(db.Model):
            id: Mapped[int] = sa.orm.mapped_column(
                sa.Identity(), primary_key=True, autoincrement=True
            )
            name: Mapped[str] = sa.orm.mapped_column(unique=True)

            __table_args__ = (sa.UniqueConstraint("name", "name"),)

        db.create_all()

        with retrying_session(db.bind) as s:
            todo = Todo(title="hello")

            s.add(todo)

        # with db.bind.Session() as session:
        #     for _ in range(5):
        #         uni = Unique(name="Joe")
        #         session.add(uni)
        #         session.commit()
        # objs = [Unique(name="Joe"), Unique(name="Joe")]
        # session.add_all(objs)

    # with retrying_async_session(ctx.Session) as s:
    #     select_todo = await s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()

    # assert select_todo == todo


# class TestBindContext(base.ComplexTestBase):
#     def test_bind_context_execution_isolation_level(self, db: SQLAlchemy, Todo: t.Type[t.Any]):
#         def add_todo():
#             with db.bind.Session() as s:
#                 with s.begin():
#                     todo = Todo(title="hello")
#                     s.add(todo)
#                     s.flush()
#                     s.refresh(todo)


# class TestTestTransaction(base.ComplexTestBase):
#     def test_test_transaction(self, db: SQLAlchemy, Todo: t.Type[t.Any]):
#         with db.bind.test_transaction(savepoint=True) as tx:
#             with tx.Session() as s:
#                 todo = Todo(title="hello")
#                 s.add(todo)
#                 s.commit()
#                 s.refresh(todo)

#             with tx.Session() as s:
#                 select_todo = s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()

#             assert select_todo == todo

#         with db.bind.Session() as s:
#             with pytest.raises(sa.orm.exc.NoResultFound):
#                 s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()
