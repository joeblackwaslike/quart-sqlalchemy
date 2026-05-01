import sqlalchemy
from blinker import Namespace

sa = sqlalchemy

signals = Namespace()


before_bind_engine_created = signals.signal(
    "simple-sqlalchemy.bind.engine.created.before",
    doc="""Called before a bind creates an engine.

    Handlers should have the following signature:
        def handler(
            sender: Bind | AsyncBind,
            config: dict[str, Any],
            prefix: str,
        ) -> None:
            ...
    """,
)
after_bind_engine_created = signals.signal(
    "simple-sqlalchemy.bind.engine.created.after",
    doc="""Called after a bind creates an engine.

    Handlers should have the following signature:
        def handler(
            sender: Bind | AsyncBind,
            config: dict[str, Any],
            prefix: str,
            engine: sa.Engine,
        ) -> None:
            ...
    """,
)

before_bind_session_factory_created = signals.signal(
    "simple-sqlalchemy.bind.session_factory.created.before",
    doc="""Called before a bind creates a session_factory.

    Handlers should have the following signature:
        def handler(sender: Bind | AsyncBind, options: dict[str, Any]) -> None:
            ...
    """,
)
after_bind_session_factory_created = signals.signal(
    "simple-sqlalchemy.bind.session_factory.created.after",
    doc="""Called after a bind creates a session_factory.

    Handlers should have the following signature:
        def handler(
            sender: Bind | AsyncBind,
            options: dict[str, Any],
            session_factory: sa.orm.sessionmaker | sa.ext.asyncio.async_sessionmaker,
        ) -> None:
            ...
    """,
)


bind_context_entered = signals.signal(
    "simple-sqlalchemy.bind.context.entered",
    doc="""Called when a bind context is entered.

    Handlers should have the following signature:
        def handler(
            sender: Bind | AsyncBind,
            engine_execution_options: dict[str, Any],
            session_execution_options: dict[str, Any],
            context: BindContext,
        ) -> None:
            ...
    """,
)

bind_context_exited = signals.signal(
    "simple-sqlalchemy.bind.context.exited",
    doc="""Called when a bind context is exited.

    Handlers should have the following signature:
        def handler(
            sender: Bind | AsyncBind,
            engine_execution_options: dict[str, Any],
            session_execution_options: dict[str, Any],
            context: BindContext,
        ) -> None:
            ...
    """,
)


before_framework_extension_initialization = signals.signal(
    "simple-sqlalchemy.framework.extension.quart.initialization.before",
    doc="""Fired before SQLAlchemy.init_app(app) is called.

    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)
after_framework_extension_initialization = signals.signal(
    "simple-sqlalchemy.framework.extension.quart.initialization.after",
    doc="""Fired after SQLAlchemy.init_app(app) is called.

    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)
