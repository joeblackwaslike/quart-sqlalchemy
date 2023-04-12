from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util

from quart_sqlalchemy.bind import AsyncBind
from quart_sqlalchemy.bind import Bind
from quart_sqlalchemy.config import AsyncBindConfig
from quart_sqlalchemy.config import SQLAlchemyConfig


sa = sqlalchemy


class SQLAlchemy:
    """
    This manager class keeps things very simple by using a few configuration conventions.

    Configuration has been simplified down to base_class and binds.

    * Everything related to ORM mapping, DeclarativeBase, registry, MetaData, etc should be
    configured by passing the a custom DeclarativeBase class as the base_class configuration
    parameter.

    * Everything related to engine/session configuration should be configured by passing a
    dictionary mapping string names to BindConfigs as the `binds` configuration parameter.

    BindConfig can be as simple as a dictionary containing a url key like so:

        bind_config = {
            "default": {"url": "sqlite://"}
        }

    But most use cases will require more than just a connection url, and divide core/engine
    configuration from orm/session configuration which looks more like this:

        bind_config = {
            "default": {
                "engine": {
                    "url": "sqlite://"
                },
                "session": {
                    "expire_on_commit": False
                }
            }
        }

    Everything under `engine` will then be passed to `sqlalchemy.create_engine_from_config` and
    everything under `session` will be passed to `sqlalchemy.orm.sessionmaker`.

        engine = sa.create_engine_from_config(bind_config.engine)
        Session = sa.orm.sessionmaker(bind=engine, **bind_config.session)

    Config Examples:

        Simple URL:
            db = SQLAlchemy(
                SQLAlchemyConfig(
                    binds=dict(
                        default=dict(
                            url="sqlite://"
                        )
                    )
                )
            )

        Shortcut for the above:
            db = SQLAlchemy(SQLAlchemyConfig())

        More complex configuration for engine and session both:
            db = SQLAlchemy(
                SQLAlchemyConfig(
                    binds=dict(
                        default=dict(
                            engine=dict(
                                url="sqlite://"
                            ),
                            session=dict(
                                expire_on_commit=False
                            )
                        )
                    )
                )
            )

    Once instantiated, operations targetting all of the binds, aka metadata, like
    `metadata.create_all` should be called from this class.  Operations specific to a bind
    should be called from that bind.  This class has a few ways to get a specific bind.

    * To get a Bind, you can call `.get_bind(name)` on this class.  The default bind can be
    referenced at `.bind`.

    * To define an ORM model using the Base class attached to this class, simply inherit
    from `.Base`

        db = SQLAlchemy(SQLAlchemyConfig())

        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()

    * You can also decouple Base from SQLAlchemy with some dependency inversion:
        from quart_sqlalchemy.model.mixins import DynamicArgsMixin, ReprMixin, TableNameMixin

        class Base(DynamicArgsMixin, ReprMixin, TableNameMixin):
            __abstract__ = True


        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db = SQLAlchemy(SQLAlchemyConfig(bind_class=Base))

        db.create_all()


    Declarative Mapping using registry based decorator:

        db = SQLAlchemy(SQLAlchemyConfig())

        @db.registry.mapped
        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Declarative with Imperative Table (Hybrid Declarative):

        class User(db.Base):
            __table__ = sa.Table(
                "user",
                db.metadata,
                sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                sa.Column("name", sa.String, default="Joe"),
            )


    Declarative using reflection to automatically build the table object:

    class User(db.Base):
        __table__ = sa.Table(
            "user",
            db.metadata,
            autoload_with=db.bind.engine,
        )


    Declarative Dataclass Mapping:

        from quart_sqlalchemy.model import Base as Base_

        class Base(sa.orm.MappedAsDataclass, Base_):
            pass

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        class User(db.Base):
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Declarative Dataclass Mapping (using decorator):

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        @db.registry.mapped_as_dataclass
        class User:
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Alternate Dataclass Provider Pattern:

        from pydantic.dataclasses import dataclass
        from quart_sqlalchemy.model import Base as Base_

        class Base(sa.orm.MappedAsDataclass, Base_, dataclass_callable=dataclass):
            pass

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        class User(db.Base):
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()

    Imperative style Mapping

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        user_table = sa.Table(
            "user",
            db.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String, default="Joe"),
        )

        post_table = sa.Table(
            "post",
            db.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("title", sa.String, default="My post"),
            sa.Column("user_id", sa.ForeignKey("user.id"), nullable=False),
        )

        class User:
            pass

        class Post:
            pass

        db.registry.map_imperatively(
            User,
            user_table,
            properties={
                "posts": sa.orm.relationship(Post, back_populates="user")
            }
        )
        db.registry.map_imperatively(
            Post,
            post_table,
            properties={
                "user": sa.orm.relationship(User, back_populates="posts", uselist=False)
            }
        )
    """

    config: SQLAlchemyConfig
    binds: t.Dict[str, t.Union[Bind, AsyncBind]]
    Base: t.Type[sa.orm.DeclarativeBase]

    def __init__(
        self,
        config: t.Optional[SQLAlchemyConfig] = None,
        initialize: bool = True,
    ):
        self.config = config

        if initialize:
            self.initialize()

    def initialize(self, config: t.Optional[SQLAlchemyConfig] = None):
        if config is not None:
            self.config = config
        if self.config is None:
            self.config = SQLAlchemyConfig.default()

        if issubclass(self.config.base_class, sa.orm.DeclarativeBase):
            Base = self.config.base_class  # type: ignore
        else:
            Base = type("Base", (self.config.base_class, sa.orm.DeclarativeBase), {})

        self.Base = Base

        if not hasattr(self, "binds"):
            self.binds = {}
            for name, bind_config in self.config.binds.items():
                is_async = isinstance(bind_config, AsyncBindConfig)
                factory = AsyncBind if is_async else Bind
                self.binds[name] = factory(name, bind_config.engine.url, bind_config, self.metadata)

    def get_bind(self, bind: str = "default"):
        return self.binds[bind]

    @property
    def bind(self) -> Bind:
        return self.get_bind()

    @property
    def metadata(self) -> sa.MetaData:
        return self.Base.metadata

    @property
    def registry(self) -> sa.orm.registry:
        return self.Base.registry

    def create_all(self, bind: str = "default"):
        return self.binds[bind].create_all()

    def drop_all(self, bind: str = "default"):
        return self.binds[bind].drop_all()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.bind.engine.url}>"
