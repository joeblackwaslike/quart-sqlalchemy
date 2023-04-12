import typing as t

from quart import Quart

from .. import signals
from ..config import SQLAlchemyConfig
from ..sqla import SQLAlchemy
from .cli import db_cli


class QuartSQLAlchemy(SQLAlchemy):
    def __init__(
        self,
        config: t.Optional[SQLAlchemyConfig] = None,
        app: t.Optional[Quart] = None,
    ):
        initialize = False if config is None else True
        super().__init__(config, initialize=initialize)

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Quart) -> None:
        if "sqlalchemy" in app.extensions:
            raise RuntimeError(
                f"A {type(self).__name__} instance has already been registered on this app"
            )

        if self.config is None:
            self.config = SQLAlchemyConfig.from_framework(app.config)
            self.initialize()

        signals.before_framework_extension_initialization.send(self, app=app)

        app.extensions["sqlalchemy"] = self

        @app.shell_context_processor
        def export_sqlalchemy_objects():
            nonlocal self

            return dict(
                db=self,
                **{m.class_.__name__: m.class_ for m in self.Base.registry.mappers},
            )

        app.cli.add_command(db_cli)

        signals.before_framework_extension_initialization.send(self, app=app)
