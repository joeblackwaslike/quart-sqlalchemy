from __future__ import annotations

import sqlalchemy
import sqlalchemy.orm
from blinker import Namespace
from quart.signals import AsyncNamespace


sa = sqlalchemy

sync_signals = Namespace()
async_signals = AsyncNamespace()


before_bind_engine_created = sync_signals.signal(
    "quart-sqlalchemy.bind.engine.created.before",
    doc="""Called before a bind creates an engine.

    Handlers should have the following signature:
        def handler(
            sender: t.Union[Bind, AsyncBind],
            config: Dict[str, Any],
            prefix: str,
        ) -> None:
            ...
    """,
)
after_bind_engine_created = sync_signals.signal(
    "quart-sqlalchemy.bind.engine.created.after",
    doc="""Called after a bind creates an engine.

    Handlers should have the following signature:
        def handler(
            sender: t.Union[Bind, AsyncBind],
            config: Dict[str, Any],
            prefix: str,
            engine: sa.Engine,
        ) -> None:
            ...
    """,
)

before_bind_session_factory_created = sync_signals.signal(
    "quart-sqlalchemy.bind.session_factory.created.before",
    doc="""Called before a bind creates a session_factory.

    Handlers should have the following signature:
        def handler(sender: t.Union[Bind, AsyncBind], options: Dict[str, Any]) -> None:
            ...
    """,
)
after_bind_session_factory_created = sync_signals.signal(
    "quart-sqlalchemy.bind.session_factory.created.after",
    doc="""Called after a bind creates a session_factory.

    Handlers should have the following signature:
        def handler(
            sender: t.Union[Bind, AsyncBind],
            options: Dict[str, Any],
            session_factory: t.Union[sa.orm.sessionmaker, sa.ext.asyncio.async_sessionmaker],
        ) -> None:
            ...
    """,
)


bind_context_entered = sync_signals.signal(
    "quart-sqlalchemy.bind.context.entered",
    doc="""Called when a bind context is entered.

    Handlers should have the following signature:
        def handler(
            sender: t.Union[Bind, AsyncBind],
            engine_execution_options: Dict[str, Any],
            session_execution_options: Dict[str, Any],
            context: BindContext,
        ) -> None:
            ...
    """,
)

bind_context_exited = sync_signals.signal(
    "quart-sqlalchemy.bind.context.exited",
    doc="""Called when a bind context is exited.

    Handlers should have the following signature:
        def handler(
            sender: t.Union[Bind, AsyncBind],
            engine_execution_options: Dict[str, Any],
            session_execution_options: Dict[str, Any],
            context: BindContext,
        ) -> None:
            ...
    """,
)


before_framework_extension_initialization = sync_signals.signal(
    "quart-sqlalchemy.framework.extension.initialization.before",
    doc="""Fired before SQLAlchemy.init_app(app) is called.
    
    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)
after_framework_extension_initialization = sync_signals.signal(
    "quart-sqlalchemy.framework.extension.initialization.after",
    doc="""Fired after SQLAlchemy.init_app(app) is called.
    
    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)


framework_extension_load_fixtures = sync_signals.signal(
    "quart-sqlalchemy.framework.extension.fixtures.load",
    doc="""Fired to load fixtures into a fresh database.

    No default signal handlers exist for this signal as the logic is very application dependent.
    This signal handler is typically triggered using the CLI:

        $ quart db fixtures load 
    
    Example:

        @signals.framework_extension_load_fixtures.connect
        def handle(sender: QuartSQLAlchemy, app: Quart):
            db = sender.get_bind("default")
            with db.Session() as session:
                with session.begin():
                    session.add_all(
                        [
                            models.User(username="user1"),
                            models.User(username="user2"),
                        ]
                    )
                    session.commit()

    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)
