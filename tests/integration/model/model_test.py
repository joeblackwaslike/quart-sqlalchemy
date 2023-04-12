from datetime import datetime

import pytest
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import Base
from quart_sqlalchemy import Bind
from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.model.model import BaseMixins


sa = sqlalchemy


class TestSQLAlchemyWithCustomModelClass:
    def test_base_class_with_declarative_preserves_class_and_table_metadata(self):
        """This is nice to have as it decouples quart and quart_sqlalchemy from the data
        models themselves.
        """

        class User(Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        db.create_all()

        with db.bind.Session() as s:
            with s.begin():
                user = User()
                s.add(user)
                s.flush()
                s.refresh(user)

        Base.registry.dispose()
        Bind._instances.clear()

    def test_sqla_class_adds_declarative_base_when_missing_from_base_class(self):
        db = SQLAlchemy(SQLAlchemyConfig(base_class=BaseMixins))

        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)

        db.create_all()

        with db.bind.Session() as s:
            with s.begin():
                user = User()
                s.add(user)
                s.flush()
                s.refresh(user)
