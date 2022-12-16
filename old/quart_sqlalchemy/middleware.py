from contextvars import ContextVar
from contextlib import AsyncExitStack
from typing import Dict, Optional, Union
import asyncio
from collections import defaultdict
from functools import partial

from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import DeclarativeMeta

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from quart_sqlalchemy import util
from quart_sqlalchemy.model import DefaultMeta, Model


try:
    from greenlet import getcurrent as ident_func
except ImportError:
    from threading import get_ident as ident_func


class MissingSessionError(Exception):
    """Excetion raised for when the user tries to access a database session before it is created."""

    def __init__(self):
        msg = """
        No session found! Either you are not currently in a request context,
        or you need to manually create a session context by using a `db` instance as
        a context manager e.g.:
        async with db():
            await db.session.execute(foo.select()).fetchall()
        """
        super().__init__(msg)


class SessionNotInitialisedError(Exception):
    """Exception raised when the user creates a new DB session without first initialising it."""

    def __init__(self):
        msg = """
        Session not initialised! Ensure that DBSessionMiddleware has been initialised before
        attempting database access.
        """
        super().__init__(msg)


class _SQLAlchemyState:
    """Remembers configuration for the (db, app) tuple."""

    def __init__(self, db):
        self.db = db
        self.connectors = {}


class SQLAlchemy:
    def __init__(
        self,
        app: Optional[ASGIApp] = None,
        engine_options: Dict = None,
        session_options: Dict = None,
        custom_engine: Optional[Engine] = None,
        use_async: bool = False,
        use_future: bool = False,
    ):
        self.engine_options = engine_options or {}
        self.session_options = session_options or {}
        self.custom_engine = custom_engine
        self.use_async = use_async
        self.use_future = use_future

        self.session_options.setdefault("autoflush", False)
        self.session_options.setdefault("expire_on_commit", False)
        self.session_options.setdefault("future", use_future)

        self.engine_options.setdefault("future", use_future)

        self._registry = dict(
            engines=defaultdict(partial(ContextVar, f"", default=None)),
            scoped_sessions=defaultdict(partial(ContextVar, f"", default=None)),
            sessions=defaultdict(partial(ContextVar, f"", default=None)),
        )

        self.Model = self.make_declarative_base()

        if app is not None:
            self.init_app(app)

    def init_app(self, app, ):
        root_app = app
        while hasattr(root_app, 'asgi_app'):
            root_app = root_app.asgi_app

        config = root_app.config
        self.engine_options.setdefault('echo', config.get("SQLALCHEMY_ECHO", False))
        self.engine_options.update(config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
        # record_queries = config.get("SQLALCHEMY_RECORD_QUERIES", None)
        db_url = config.get('SQLALCHEMY_DATABASE_URI', None)

        if db_url is None:
            raise ValueError("You need to pass a db_url or a custom_engine parameter.")

        self.engine_options = util.apply_driver_hacks(db_url, app.root_path, self.engine_options)

        if not self.custom_engine:
            engine = self.create_engine(db_url, self.engine_options, use_async=self.use_async)
        else:
            engine = self.custom_engine

        self._registry['scoped_sessions']['default'] = self.create_scoped_session(
            engine,
            self.session_options,
        )
        
        app.extensions["sqlalchemy"] = _SQLAlchemyState(self)

    def make_declarative_base(self, model=Model, metadata=None):
        """Creates the declarative base that all models will inherit from.

        :param model: base model class (or a tuple of base classes) to pass
            to :func:`~sqlalchemy.ext.declarative.declarative_base`. Or a class
            returned from ``declarative_base``, in which case a new base class
            is not created.
        :param metadata: :class:`~sqlalchemy.MetaData` instance to use, or
            none to use SQLAlchemy's default.

        .. versionchanged 2.3.0::
            ``model`` can be an existing declarative base in order to support
            complex customization such as changing the metaclass.
        """
        if not isinstance(model, DeclarativeMeta):
            model = declarative_base(
                cls=model, name="Model", metadata=metadata, metaclass=DefaultMeta
            )

        # if user passed in a declarative base and a metaclass for some reason,
        # make sure the base uses the metaclass
        if metadata is not None and model.metadata is not metadata:
            model.metadata = metadata

        if self.use_async:
            getattr(model, '__mapper_args__', {}).setdefault('eager_defaults', True)

        return model

    def create_engine(self, db_url, engine_options, use_async=False):
        if use_async:
            factory = create_async_engine
        else:
            factory = create_engine

        return factory(db_url, **engine_options)

    def create_scoped_session(self, engine, session_options):
        if self.use_async:
            scopefunc = session_options.get('scopefunc', asyncio.current_task)
            class_ = AsyncSession
        else:
            scopefunc = session_options.get('scopefunc', ident_func)
            class_ = None

        session = sessionmaker(
            engine,
            class_=class_,
            **self.session_options,
        )

        return scoped_session(session, scopefunc=scopefunc)

    def session(self, name="default"):
        return DBSession(name, self._registry)

    def __repr__(self):
        urls = [e.url for e in self._registry['engines'].values()]
        if len(urls) == 0:
            urls = ""
        elif len(urls) == 1:
            urls = urls[0]
        else:
            urls = ' '.join(urls)        
        # url = self.engine.url if self.app or current_app else None
        return f"<{type(self).__name__} engine={urls!r}>"


class DBSessionMeta(type):
    # using this metaclass means that we can access db.session as a property at a class level,
    # rather than db().session
    @property
    def session(self) -> AsyncSession:
        """Return an instance of Session local to the current async context."""
        if self.name not in self._registry['scoped_sessions']:
            raise SessionNotInitialisedError

        session = self._registry['scoped_sessions'][self.name].get()
        if session is None:
            raise MissingSessionError

        return session


class DBSession(metaclass=DBSessionMeta):
    def __init__(self, name="default", registry, session_options: Dict = None):
        self.name = name
        self._registry = registry
        self.session_options = session_options or {}
        self.session_options.setdefault('commit_on_exit', False)
        self.token = None

    def _push_session(self):
        if self.name not in self._registry['scoped_sessions'] or not isinstance(
            self._registry['scoped_sessions'][self.name].get(), sessionmaker
        ):
            raise SessionNotInitialisedError

        token = self._registry['scoped_sessions'][self.name].set(**self.session_options)
        # if self.name not in self._registry['sessions']:
        #     self._registry['sessions'][self.name] = ContextVar(f"_sessions_{self.name}", default=None)
        self.token = self._registry['sessions'][self.name].set(token)

    def __enter__(self):
        self._push_session()
        return self

    async def __aenter__(self):
        self._push_session()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        session = self._registry['sessions'][self.name].get()
        if exc_type is not None:
            session.rollback()

        if self.session_options['commit_on_exit']:
            session.commit()

        session.close()
        self._registry['sessions'][self.name].reset(self.token)

    async def __aexit__(self, exc_type, exc_value, traceback):
        session = self._registry['sessions'][self.name].get()
        if exc_type is not None:
            await session.rollback()

        if self.session_options['commit_on_exit']:
            await session.commit()

        await session.close()
        self._registry['sessions'][self.name].reset(self.token)

