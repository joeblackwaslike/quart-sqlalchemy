import click
import sqlalchemy as sa
from quart import g
from quart import request
from quart.cli import AppGroup
from quart.cli import pass_script_info
from quart.cli import ScriptInfo
from sqlalchemy.types import Integer
from sqlalchemy.types import TypeDecorator

from quart_sqlalchemy import Base
from quart_sqlalchemy import SQLAlchemyConfig
from quart_sqlalchemy.framework import QuartSQLAlchemy
from quart_sqlalchemy.sim.util import ObjectID


cli = AppGroup("db-schema")


class ObjectIDType(TypeDecorator):
    """A custom database column type that converts integer value to our ObjectID.
    This allows us to pass around ObjectID type in the application for easy
    frontend encoding and database decoding on the integer value.

    Note: all id db column type should use this type for its column.
    """

    impl = Integer
    cache_ok = False

    def process_bind_param(self, value, dialect):
        """Data going into to the database will be transformed by this method.
        See ``ObjectID`` for the design and rational for this.
        """
        if value is None:
            return None

        return ObjectID(value).decode()

    def process_result_value(self, value, dialect):
        """Data going out from the database will be explicitly casted to the
        ``ObjectID``.
        """
        if value is None:
            return None

        return ObjectID(value)


class MyBase(Base):
    type_annotation_map = {ObjectID: ObjectIDType}


class MyQuartSQLAlchemy(QuartSQLAlchemy):
    def init_app(self, app):
        super().init_app(app)

        @app.before_request
        def set_bind():
            if request.method in ["GET", "OPTIONS", "HEAD", "TRACE"]:
                g.bind = self.get_bind("read-replica")
            else:
                g.bind = self.get_bind("default")

        app.cli.add_command(cli)


@cli.command("load")
@pass_script_info
def schema_load(info: ScriptInfo) -> None:
    app = info.load_app()
    db = app.extensions.get("sqlalchemy")
    db.create_all()

    click.echo(f"Initialized database schema for {db}")


# sqlite:///file:mem.db?mode=memory&cache=shared&uri=true
db = MyQuartSQLAlchemy(
    SQLAlchemyConfig.parse_obj(
        {
            "model_class": MyBase,
            "binds": {
                "default": {
                    "engine": {"url": "sqlite:///file:sim.db?cache=shared&uri=true"},
                    "session": {"expire_on_commit": False},
                },
                "read-replica": {
                    "engine": {"url": "sqlite:///file:sim.db?cache=shared&uri=true"},
                    "session": {"expire_on_commit": False},
                    "read_only": True,
                },
                "async": {
                    "engine": {"url": "sqlite+aiosqlite:///file:sim.db?cache=shared&uri=true"},
                    "session": {"expire_on_commit": False},
                },
            },
        }
    )
)
