from __future__ import annotations

import typing as t
from dataclasses import dataclass

import sqlalchemy
import sqlalchemy.orm
from blinker import Namespace
from quart import Quart
from quart.signals import AsyncNamespace
from sqlalchemy.engine import Engine

from .types import AnyCallableType
from .types import ScopedSessionFactoryType
from .types import SessionFactoryType


sa = sqlalchemy

sync_signals = Namespace()
async_signals = AsyncNamespace()

before_engine_created = sync_signals.signal("quart-sqlalchemy.engine.created.before")
after_engine_created = sync_signals.signal("quart-sqlalchemy.engine.created.after")

before_app_initialized = sync_signals.signal(
    "quart-sqlalchemy.app.initialized.before",
    doc="""Fired before SQLAlchemy.init_app(app) is called.
    
    Handler signature:
        def handle(sender: SQLAlchemy, app: Quart):
            ...
    """,
)
after_app_initialized = sync_signals.signal(
    "quart-sqlalchemy.app.initialized.after",
    doc="""Fired after SQLAlchemy.init_app(app) is called.
    
    Handler signature:
        def handle(sender: SQLAlchemy, app: Quart):
            ...
    """,
)

before_make_session_factory = sync_signals.signal("quart-sqlalchemy.make-session-factory.before")
after_make_session_factory = sync_signals.signal("quart-sqlalchemy.make-session-factory.after")

before_make_scoped_session = sync_signals.signal("quart-sqlalchemy.make-scoped-session.before")
after_make_scoped_session = sync_signals.signal("quart-sqlalchemy.make-scoped-session.after")


@dataclass
class EngineContext:
    bind_key: t.Optional[str]
    options: dict[str, t.Any]
    app: Quart
    factory: t.Callable[[dict[str, t.Any], str], Engine]
    url: sa.URL
    is_async: bool


@dataclass
class SessionmakerContext:
    is_async: bool
    options: dict[str, t.Any]
    factory: AnyCallableType


@dataclass
class ScopedSessionContext:
    is_async: bool
    scopefunc: t.Callable[[], int]
    options: dict[str, t.Any]
    session_factory: t.Callable[[dict[str, t.Any], bool], SessionFactoryType]
    scoped_session_factory: ScopedSessionFactoryType
