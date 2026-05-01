import inspect

from fastapi import FastAPI

from ... import signals
from ...config import SQLAlchemyConfig
from ...sqla import SQLAlchemy


class FastAPISQLAlchemy(SQLAlchemy):
    """FastAPI integration for SQLAlchemy.

    Provides FastAPI-specific integration including:
    - App state management via app.state
    - Lifespan event integration for startup/shutdown
    - Async-first design matching FastAPI patterns

    Example:
        >>> from fastapi import FastAPI
        >>> from quart_sqlalchemy import SQLAlchemyConfig, BindConfig
        >>> from quart_sqlalchemy.framework.fastapi import FastAPISQLAlchemy
        >>>
        >>> config = SQLAlchemyConfig(
        ...     binds={"default": BindConfig(url="sqlite+aiosqlite:///:memory:")}
        ... )
        >>> app = FastAPI()
        >>> db = FastAPISQLAlchemy(config, app=app)
    """

    def __init__(
        self,
        config: SQLAlchemyConfig,
        app: FastAPI | None = None,
    ):
        super().__init__(config)
        if app is not None:
            self.init_app(app)

    def init_app(self, app: FastAPI) -> None:
        """Initialize the SQLAlchemy extension with a FastAPI app.

        Args:
            app: The FastAPI application instance.

        Raises:
            RuntimeError: If SQLAlchemy is already registered on this app.
        """
        if hasattr(app.state, "sqlalchemy"):
            raise RuntimeError(
                f"A {type(self).__name__} instance has already been registered on this app"
            )

        signals.before_framework_extension_initialization.send(self, app=app)

        app.state.sqlalchemy = self

        async def shutdown_db() -> None:
            """Dispose of database connections on app shutdown."""
            for bind in self.binds.values():
                if hasattr(bind, "engine") and hasattr(bind.engine, "dispose"):
                    if inspect.iscoroutinefunction(bind.engine.dispose):
                        await bind.engine.dispose()
                    else:
                        bind.engine.dispose()

        app.router.add_event_handler("shutdown", shutdown_db)

        signals.after_framework_extension_initialization.send(self, app=app)
