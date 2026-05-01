import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy_utils

sa = sqlalchemy
sau = sqlalchemy_utils

"""
Use PEP 695 type keyword to create a generic primary key column.

- details: https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#mapping-whole-column-declarations-to-generic-python-types
- pep: https://peps.python.org/pep-0695/


Example Usage:
    import uuid


    class Base(DeclarativeBase):
        pass


    class A(Base):
        __tablename__ = "a"

        # will create an Integer primary key
        id: Mapped[PrimaryKey[int]]


    class B(Base):
        __tablename__ = "b"

        # will create a UUID primary key
        id: Mapped[PrimaryKey[uuid.UUID]]
"""
type PrimaryKey[T] = t.Annotated[T, sa.orm.mapped_column(primary_key=True)]

CreatedTimestamp = t.Annotated[
    datetime, sa.orm.mapped_column(server_default=sa.func.UTC_TIMESTAMP())
]
UpdatedTimestamp = t.Annotated[
    datetime,
    sa.orm.mapped_column(
        server_default=sa.func.UTC_TIMESTAMP(),
        server_onupdate=sa.func.UTC_TIMESTAMP(),
    ),
]
Json = t.Annotated[
    dict[t.Any, t.Any],
    sa.orm.mapped_column(sau.JSONType, default_factory=dict),
]
