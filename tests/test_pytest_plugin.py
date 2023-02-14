# from __future__ import annotations

# import typing as t

# import pytest
# import sqlalchemy
# import sqlalchemy.orm
# from quart import Quart

# from quart_sqlalchemy import SQLAlchemy
# from quart_sqlalchemy.testing.base import SQLAlchemyBase


# sa = sqlalchemy


# class TestSQLAlchemyBase(SQLAlchemyBase):
#     async def test_session_behavior(
#         self,
#         app: Quart,
#         db: SQLAlchemy,
#         Todo: t.Any,
#     ):
#         async with app.app_context():
#             with db.session() as session:
#                 session.add(Todo())
#                 session.commit()

#                 result = session.execute(db.select(Todo).where(Todo.id == 1)).scalar_one()
#                 assert result
