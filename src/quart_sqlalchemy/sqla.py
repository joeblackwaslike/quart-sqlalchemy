from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util

from .bind import AsyncBind
from .bind import Bind
from .config import AsyncBindConfig
from .config import SQLAlchemyConfig


sa = sqlalchemy


class SQLAlchemy:
    config: SQLAlchemyConfig
    binds: t.Dict[str, t.Union[Bind, AsyncBind]]
    Model: t.Type[sa.orm.DeclarativeBase]

    def __init__(self, config: SQLAlchemyConfig, initialize: bool = True):
        self.config = config

        if initialize:
            self.initialize()

    def initialize(self):
        if issubclass(self.config.model_class, sa.orm.DeclarativeBase):
            Model = self.config.model_class  # type: ignore
        else:

            class Model(self.config.model_class, sa.orm.DeclarativeBase):
                pass

        self.Model = Model

        self.binds = {}
        for name, bind_config in self.config.binds.items():
            is_async = isinstance(bind_config, AsyncBindConfig)
            if is_async:
                self.binds[name] = AsyncBind(bind_config, self.metadata)
            else:
                self.binds[name] = Bind(bind_config, self.metadata)

    @classmethod
    def default(cls):
        return cls(SQLAlchemyConfig())

    @property
    def bind(self) -> Bind:
        return self.get_bind()

    @property
    def metadata(self) -> sa.MetaData:
        return self.Model.metadata

    def get_bind(self, bind: str = "default"):
        return self.binds[bind]

    def create_all(self, bind: str = "default"):
        return self.binds[bind].create_all()

    def drop_all(self, bind: str = "default"):
        return self.binds[bind].drop_all()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.bind.engine.url}>"
