import typing as t

from quart import Quart

from .. import signals
from ..config import SQLAlchemyConfig
from ..sqla import SQLAlchemy
from .cli import db_cli


class QuartSQLAlchemy(SQLAlchemy):
    def __init__(
        self,
        config: SQLAlchemyConfig,
        app: t.Optional[Quart] = None,
    ):
        super().__init__(config)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Quart) -> None:
        if "sqlalchemy" in app.extensions:
            raise RuntimeError(
                f"A {type(self).__name__} instance has already been registered on this app"
            )

        signals.before_framework_extension_initialization.send(self, app=app)

        app.extensions["sqlalchemy"] = self

        @app.shell_context_processor
        def export_sqlalchemy_objects():
            return dict(
                db=self,
                **{m.class_.__name__: m.class_ for m in self.Model._sa_registry.mappers},
            )

        app.cli.add_command(db_cli)

        signals.before_framework_extension_initialization.send(self, app=app)
