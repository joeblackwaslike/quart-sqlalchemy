from __future__ import annotations

import os
import typing as t
from copy import deepcopy
from dataclasses import dataclass
from dataclasses import field
from dataclasses import InitVar
from weakref import WeakKeyDictionary

import quart
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from quart import has_app_context
from quart import Quart
from quart.globals import app_ctx

from . import signals
from .model import _QueryProperty
from .model import DefaultMeta
from .model import Model as CustomModel
from .query import Query as CustomQuery
from .session import _app_ctx_id
from .session import async_scoped_session
from .session import RoutingSession
from .session import scoped_session
from .signals import EngineContext
from .signals import ScopedSessionContext
from .signals import SessionmakerContext
from .table import _Table
from .testing.transaction import SyncTestTransaction
from .types import ScopedSessionType
from .types import SessionType


sa = sqlalchemy


class SQLAlchemy:
    """Integrates SQLAlchemy with Quart. This handles setting up one or more engines,
    associating tables and models with specific engines, and cleaning up connections and
    sessions after each request.

    Only the engine configuration is specific to each application, other things like
    the model, table, metadata, and session are shared for all applications using that
    extension instance. Call :meth:`init_app` to configure the extension on an
    application.

    After creating the extension, create model classes by subclassing :attr:`Model`, and
    table classes with :attr:`sa.Table`. These can be accessed before :meth:`init_app` is
    called, making it possible to define the models separately from the application.

    Accessing :attr:`session` and :attr:`engine` requires an active Quart application
    context. This includes methods like :meth:`create_all` which use the engine.

    This class also provides access to names in SQLAlchemy's ``sqlalchemy`` and
    ``sqlalchemy.orm`` modules. For example, you can use ``db.Column`` and
    ``db.relationship`` instead of importing ``sqlalchemy.Column`` and
    ``sqlalchemy.orm.relationship``. This can be convenient when defining models.

    :param app: Call :meth:`init_app` on this Quart application now.
    :param metadata: Use this as the default :class:`sqlalchemy.schema.MetaData`. Useful
        for setting a naming convention.
    :param session_options: Arguments used by :attr:`session` to create each session
        instance. A ``scopefunc`` key will be passed to the scoped session, not the
        session instance. See :class:`sqlalchemy.orm.sessionmaker` for a list of
        arguments.
    :param query_class: Use this as the default query class for models and dynamic
        relationships. The query interface is considered legacy in SQLAlchemy.
    :param model_class: Use this as the model base class when creating the declarative
        model class :attr:`Model`. Can also be a fully created declarative model class
        for further customization.
    :param engine_options: Default arguments used when creating every engine. These are
        lower precedence than application config. See :func:`sqlalchemy.create_engine`
        for a list of arguments.
    :param add_models_to_shell: Add the ``db`` instance and all model classes to
        ``quart shell``.
    """

    metadatas: dict[str | None, sa.MetaData]
    Model: type[t.Any]
    Table: type[sa.Table]
    Query: type[sa.orm.Query]

    _scoped_sessions: dict[str | None, ScopedSessionType]
    _app_engines: WeakKeyDictionary[Quart, dict[str | None, sa.Engine]]
    _session_class: type[sa.orm.Session]
    _engine_options: dict[str, t.Any]
    _session_options: dict[str, t.Any]
    _add_models_to_shell: bool
    _last_app_ctx: t.Optional[quart.ctx.AppContext]
    _context_caching_enabled: bool
    _is_async_session: bool

    def __init__(
        self,
        app: Quart | None = None,
        *,
        metadata: t.Optional[sa.MetaData] = None,
        session_options: t.Optional[dict[str, t.Any]] = None,
        session_scopefunc: t.Callable[[], int] = _app_ctx_id,
        session_class: type[sa.orm.Session] = RoutingSession,
        is_async_session: bool = False,
        query_class: type[sa.orm.Query] = CustomQuery,
        model_class: type[t.Any] | sa.orm.DeclarativeMeta = CustomModel,
        engine_options: t.Optional[dict[str, t.Any]] = None,
        add_models_to_shell: bool = True,
        context_caching_enabled: bool = False,
    ):
        self._session_options = session_options or {}
        self._is_async_session = is_async_session

        self.Query = query_class
        """The default query class used by ``Model.query`` and ``lazy="dynamic"``
        relationships.

        .. warning::
            The query interface is considered legacy in SQLAlchemy.

        Customize this by passing the ``query_class`` parameter to the extension.
        """

        self.metadatas = {}
        """Map of bind keys to :class:`sqlalchemy.schema.MetaData` instances. The
        ``None`` key refers to the default metadata, and is available as
        :attr:`metadata`.

        Customize the default metadata by passing the ``metadata`` parameter to the
        extension. This can be used to set a naming convention. When metadata for
        another bind key is created, it copies the default's naming convention.
        """
        if metadata is not None:
            metadata.info["bind_key"] = None
            self.metadatas[None] = metadata

        self.Table = self._make_table_class()
        """A :class:`sqlalchemy.schema.Table` class that chooses a metadata
        automatically.

        Unlike the base ``Table``, the ``metadata`` argument is not required. If it is
        not given, it is selected based on the ``bind_key`` argument.

        :param bind_key: Used to select a different metadata.
        :param args: Arguments passed to the base class. These are typically the table's
            name, columns, and constraints.
        :param kwargs: Arguments passed to the base class.
        """

        self.Model = self._make_declarative_base(model_class)
        """A SQLAlchemy declarative model class. Subclass this to define database
        models.

        If a model does not set ``__tablename__``, it will be generated by converting
        the class name from ``CamelCase`` to ``snake_case``. It will not be generated
        if the model looks like it uses single-table inheritance.

        If a model or parent class sets ``__bind_key__``, it will use that metadata and
        database engine. Otherwise, it will use the default :attr:`metadata` and
        :attr:`engine`. This is ignored if the model sets ``metadata`` or ``__table__``.

        Customize this by subclassing :class:`.Model` and passing the ``model_class``
        parameter to the extension. A fully created declarative model class can be
        passed as well, to use a custom metaclass.
        """
        self._add_models_to_shell = add_models_to_shell

        self._engine_options = engine_options or {}
        self._app_engines = WeakKeyDictionary()

        self.session_scopefunc = session_scopefunc
        self._session_class = session_class

        self.session = self._make_scoped_session(
            self._session_options, is_async=self._is_async_session
        )
        # """A :class:`sa.orm.scoped_session` that creates instances of
        # :class:`.Session` scoped to the current Quart application context. The session
        # will be removed, returning the engine connection to the pool, when the
        # application context exits.

        # Customize this by passing ``session_options`` to the extension.

        # This requires that a Quart application context is active.
        # """

        self._context_caching_enabled = context_caching_enabled
        self._last_app_ctx = None

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Quart) -> None:
        """Initialize a Quart application for use with this extension instance. This
        must be called before accessing the database engine or session with the app.

        This sets default configuration values, then configures the extension on the
        application and creates the engines for each bind key. Therefore, this must be
        called after the application has been configured. Changes to application config
        after this call will not be reflected.

        The following keys from ``app.config`` are used:

        - :data:`.SQLALCHEMY_DATABASE_URI`
        - :data:`.SQLALCHEMY_ENGINE_OPTIONS`
        - :data:`.SQLALCHEMY_ECHO`
        - :data:`.SQLALCHEMY_BINDS`
        - :data:`.SQLALCHEMY_RECORD_QUERIES`
        - :data:`.SQLALCHEMY_TRACK_MODIFICATIONS`

        :param app: The Quart application to initialize.
        """

        signals.before_app_initialized.send(self, app=app)

        if "sqlalchemy" in app.extensions:
            raise RuntimeError(
                "A 'SQLAlchemy' instance has already been registered on this Flask app."
                " Import and use that instance instead."
            )

        app.extensions["sqlalchemy"] = self
        app.teardown_appcontext(self._teardown_session)
        app.teardown_appcontext(self._teardown_async_session)

        if self._add_models_to_shell:
            from .cli import add_models_to_shell

            app.shell_context_processor(add_models_to_shell)

        basic_uri: str | sa.URL | None = app.config.setdefault(
            "SQLALCHEMY_DATABASE_URI", None
        )
        basic_engine_options = self._engine_options.copy()
        basic_engine_options.update(
            app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {})
        )
        echo: bool = app.config.setdefault("SQLALCHEMY_ECHO", False)
        config_binds: dict[
            str | None, str | sa.URL | dict[str, t.Any]
        ] = app.config.setdefault("SQLALCHEMY_BINDS", {})
        engine_options: dict[str | None, dict[str, t.Any]] = {}

        # Build the engine config for each bind key.
        for key, value in config_binds.items():
            engine_options[key] = self._engine_options.copy()

            if isinstance(value, (str, sa.URL)):
                engine_options[key]["url"] = value
            else:
                engine_options[key].update(value)

        # Build the engine config for the default bind key.
        if basic_uri is not None:
            basic_engine_options["url"] = basic_uri

        if "url" in basic_engine_options:
            engine_options.setdefault(None, {}).update(basic_engine_options)

        if not engine_options:
            raise RuntimeError(
                "Either 'SQLALCHEMY_DATABASE_URI' or 'SQLALCHEMY_BINDS' must be set."
            )

        engines = self._app_engines.setdefault(app, {})

        # Dispose existing engines in case init_app is called again.
        if engines:
            for engine in engines.values():
                engine.dispose()

            engines.clear()

        # Create the metadata, engine, and scoped_session for each bind key.
        for key, options in engine_options.items():
            self._make_metadata(key)
            options.setdefault("echo", echo)
            options.setdefault("echo_pool", echo)
            self._apply_driver_defaults(options, app)
            engines[key] = self._make_engine(key, options, app)

        if app.config.setdefault("SQLALCHEMY_RECORD_QUERIES", False):
            from . import record_queries

            for engine in engines.values():
                record_queries._listen(engine)

        if self._context_caching_enabled:

            @quart.signals.appcontext_pushed.connect_via(app)
            def _handle_appcontext_pushed(app: Quart):
                nonlocal self
                self._last_app_ctx = app_ctx._get_current_object()

        signals.after_app_initialized.send(self, app=app)

    def _make_scoped_session(
        self,
        options: dict[str, t.Any],
        is_async: bool = False,
    ) -> t.Union[scoped_session, async_scoped_session]:
        """Create a :class:`sqlalchemy.orm.scoping.scoped_session` around the factory
        from :meth:`_make_session_factory`. The result is available as :attr:`session`.

        The scope function can be customized using the ``scopefunc`` key in the
        ``session_options`` parameter to the extension. By default it uses the current
        thread or greenlet id.

        This method is used for internal setup. Its signature may change at any time.

        :param options: The ``session_options`` parameter from ``__init__``. Keyword
            arguments passed to the session factory. A ``scopefunc`` key is popped.
        """
        options = options.copy()

        context = ScopedSessionContext(
            is_async=is_async,
            scopefunc=options.pop("scopefunc", self.get_session_scope),
            options=options,
            session_factory=self._make_session_factory,
            scoped_session_factory=async_scoped_session if is_async else scoped_session,
        )

        signals.before_make_scoped_session.send(self, context=context)

        factory = context.session_factory(context.options, is_async=is_async)
        session = context.scoped_session_factory(
            factory,  # type: ignore
            scopefunc=context.scopefunc,
        )

        signals.after_make_scoped_session.send(self, scoped_session=session)

        return session

    def _make_session_factory(
        self,
        options: dict[str, t.Any],
        is_async: bool = False,
    ) -> SessionType:
        """Create the SQLAlchemy :class:`sqlalchemy.orm.sessionmaker` used by
        :meth:`_make_scoped_session`.

        To customize, pass the ``session_options`` parameter to :class:`SQLAlchemy`. To
        customize the session class, subclass :class:`.Session` and pass it as the
        ``class_`` key.

        This method is used for internal setup. Its signature may change at any time.

        :param options: The ``session_options`` parameter from ``__init__``. Keyword
            arguments passed to the session factory.
        """
        options = options.copy()

        options.setdefault("db", self)
        options.setdefault("query_cls", self.Query)
        options.setdefault("expire_on_commit", False)

        if is_async:
            options.setdefault("sync_session_class", self._session_class)
            factory = sa.ext.asyncio.async_sessionmaker
        else:
            options.setdefault("class_", self._session_class)
            factory = sa.orm.sessionmaker

        context = SessionmakerContext(
            is_async=is_async,
            options=options,
            factory=factory,
        )

        signals.before_make_session_factory.send(self, context=context)

        session_factory = context.factory(**context.options)

        signals.after_make_session_factory.send(self, session_factory=session_factory)

        return session_factory

    def test_transaction(self, bind_key: t.Optional[str] = None, savepoint=True):
        return SyncTestTransaction(self, bind_key, savepoint=savepoint)

    def _teardown_session(self, exc: BaseException | None) -> None:
        """Remove the current session at the end of the request."""
        if isinstance(self.session, sa.orm.scoped_session):
            self.session.remove()

    async def _teardown_async_session(self, exc: BaseException | None) -> None:
        """Remove the current session at the end of the request."""
        if isinstance(self.session, sa.ext.asyncio.async_scoped_session):
            await self.session.remove()

    def _make_metadata(self, bind_key: str | None) -> sa.MetaData:
        """Get or create a :class:`sqlalchemy.schema.MetaData` for the given bind key.

        This method is used for internal setup. Its signature may change at any time.

        :param bind_key: The name of the metadata being created.
        """
        if bind_key in self.metadatas:
            return self.metadatas[bind_key]

        if bind_key is not None:
            # Copy the naming convention from the default metadata.
            naming_convention = self._make_metadata(None).naming_convention
        else:
            naming_convention = None

        # Set the bind key in info to be used by session.get_bind.
        metadata = sa.MetaData(
            naming_convention=naming_convention, info={"bind_key": bind_key}
        )
        self.metadatas[bind_key] = metadata
        return metadata

    def _make_table_class(self) -> type[sa.Table]:
        """Create a SQLAlchemy :class:`sqlalchemy.schema.Table` class that chooses a
        metadata automatically based on the ``bind_key``. The result is available as
        :attr:`Table`.

        This method is used for internal setup. Its signature may change at any time.
        """

        class Table(_Table):
            def __new__(
                cls, *args: t.Any, bind_key: str | None = None, **kwargs: t.Any
            ) -> Table:
                # If a metadata arg is passed, go directly to the base Table. Also do
                # this for no args so the correct error is shown.
                if not args or (len(args) >= 2 and isinstance(args[1], sa.MetaData)):
                    return super().__new__(cls, *args, **kwargs)

                metadata = self._make_metadata(bind_key)
                return super().__new__(cls, *[args[0], metadata, *args[1:]], **kwargs)

        return Table

    def _make_declarative_base(
        self, model: type[CustomModel] | sa.orm.DeclarativeMeta
    ) -> type[t.Any]:
        """Create a SQLAlchemy declarative model class. The result is available as
        :attr:`Model`.

        To customize, subclass :class:`.Model` and pass it as ``model_class`` to
        :class:`SQLAlchemy`. To customize at the metaclass level, pass an already
        created declarative model class as ``model_class``.

        This method is used for internal setup. Its signature may change at any time.

        :param model: A model base class, or an already created declarative model class.
        """
        if not isinstance(model, sa.orm.DeclarativeMeta):
            metadata = self._make_metadata(None)
            model = sa.orm.declarative_base(
                metadata=metadata, cls=model, name="Model", metaclass=DefaultMeta
            )

        if None not in self.metadatas:
            # Use the model's metadata as the default metadata.
            model.metadata.info["bind_key"] = None  # type: ignore[union-attr]
            self.metadatas[None] = model.metadata  # type: ignore[union-attr]
        else:
            # Use the passed in default metadata as the model's metadata.
            model.metadata = self.metadatas[None]  # type: ignore[union-attr]

        model.query_class = self.Query
        model.query = _QueryProperty()
        model.__fsa__ = self
        return model

    # def _make_declarative_base_20(self, model):
    #     # if None not in self.metadatas:
    #     #     # Use the model's metadata as the default metadata.
    #     #     model.metadata.info["bind_key"] = None  # type: ignore[union-attr]
    #     #     self.metadatas[None] = model.metadata  # type: ignore[union-attr]
    #     # else:
    #     #     # Use the passed in default metadata as the model's metadata.
    #     #     model.metadata = self.metadatas[None]  # type: ignore[union-attr]
    #     model.metadata.info.setdefault("bind_key", None)

    #     bind_key = model.metadata.info["bind_key"]

    #     if None not in self.metadatas:
    #         self.metadatas[None] = model.metadata
    #     elif self.metadatas[bind_key] != model.metadata:
    #         self.metadatas[bind_key] = model.metadata

    #     model.query_class = self.Query
    #     model.query = _QueryProperty()
    #     # model.__fsa__ = self
    #     return model

    def _apply_driver_defaults(self, options: dict[str, t.Any], app: Quart) -> None:
        """Apply driver-specific configuration to an engine.

        SQLite in-memory databases use ``StaticPool`` and disable ``check_same_thread``.
        File paths are relative to the app's :attr:`~quart.Quart.instance_path`,
        which is created if it doesn't exist.

        MySQL sets ``charset="utf8mb4"``, and ``pool_timeout`` defaults to 2 hours.

        This method is used for internal setup. Its signature may change at any time.

        :meta private:

        :param options: Arguments passed to the engine.
        :param app: The application that the engine configuration belongs to.
        """
        url = sa.make_url(options["url"])
        driver = url.drivername

        if driver.startswith("sqlite"):
            if url.database is None or url.database in {"", ":memory:"}:
                options["poolclass"] = sa.StaticPool

                if "connect_args" not in options:
                    options["connect_args"] = {}

                options["connect_args"]["check_same_thread"] = False
            else:
                # the url might look like sqlite:///file:path?uri=true
                is_uri = bool(url.query.get("uri", False))
                mode = url.query.get("mode", "")

                if is_uri and mode == "memory":
                    return

                db_str = url.database[5:] if is_uri else url.database
                if not os.path.isabs(db_str):
                    os.makedirs(app.instance_path, exist_ok=True)
                    db_str = os.path.join(app.instance_path, db_str)

                    if is_uri:
                        db_str = f"file:{db_str}"

                    options["url"] = url.set(database=db_str)
        elif driver.startswith("mysql"):
            # set queue defaults only when using queue pool
            if "pool_class" not in options or options["pool_class"] is sa.QueuePool:
                options.setdefault("pool_recycle", 7200)

            if "charset" not in url.query:
                options["url"] = url.update_query_dict({"charset": "utf8mb4"})

    def _make_engine(
        self, bind_key: str | None, options: dict[str, t.Any], app: Quart
    ) -> sa.Engine:
        """Create the :class:`sqlalchemy.engine.Engine` for the given bind key and app.

        To customize, use :data:`.SQLALCHEMY_ENGINE_OPTIONS` or
        :data:`.SQLALCHEMY_BINDS` config. Pass ``engine_options`` to :class:`SQLAlchemy`
        to set defaults for all engines.

        This method is used for internal setup. Its signature may change at any time.

        :meta private:

        :param bind_key: The name of the engine being created.
        :param options: Arguments passed to the engine.
        :param app: The application that the engine configuration belongs to.
        """
        options = deepcopy(options)

        url = sa.make_url(options["url"])
        is_async = url.get_dialect().is_async
        factory = (
            sa.ext.asyncio.async_engine_from_config
            if is_async
            else sa.engine_from_config
        )
        context = EngineContext(
            bind_key=bind_key,
            options=options,
            app=app,
            factory=factory,
            url=url,
            is_async=is_async,
        )

        signals.before_engine_created.send(self, context=context)

        engine = context.factory(context.options, prefix="")

        signals.after_engine_created.send(self, engine=engine)

        return engine

    @property
    def metadata(self) -> sa.MetaData:
        """The default metadata used by :attr:`Model` and :attr:`sa.Table` if no bind key
        is set.
        """
        return self.metadatas[None]

    @property
    def engines(self) -> t.Mapping[t.Optional[str], sa.Engine]:
        """Map of bind keys to :class:`sqlalchemy.engine.Engine` instances for current
        application. The ``None`` key refers to the default engine, and is available as
        :attr:`engine`.

        To customize, set the :data:`.SQLALCHEMY_BINDS` config, and set defaults by
        passing the ``engine_options`` parameter to the extension.

        This requires that a Quart application context is active.
        """

        app = self._get_app_context().app

        if app not in self._app_engines:
            raise RuntimeError(
                "The current Quart app is not registered with this 'SQLAlchemy'"
                " instance. Did you forget to call 'init_app', or did you create"
                " multiple 'SQLAlchemy' instances?"
            )
        return self._app_engines[app]

    @property
    def engine(self) -> sa.Engine:
        """The default :class:`~sqlalchemy.engine.Engine` for the current application,
        used by :attr:`session` if the :attr:`Model` or :attr:`sa.Table` being queried does
        not set a bind key.

        To customize, set the :data:`.SQLALCHEMY_ENGINE_OPTIONS` config, and set
        defaults by passing the ``engine_options`` parameter to the extension.

        This requires that a Quart application context is active.
        """
        return self.engines[None]

    def get_bind(self, bind_key: t.Optional[str] = None, app: t.Optional[Quart] = None):
        app_engines = self._app_engines
        if not app_engines:
            raise RuntimeError("No engines created yet, call init_app first")

        if app is None:
            try:
                app_ctx = self._get_app_context(cache_fallback_enabled=True)
                app = app_ctx.app
            except RuntimeError:
                apps = tuple(app_engines.keys())
                if len(apps) > 1:
                    raise RuntimeError(
                        "No application context, multiple applications registered"
                    )
                app = apps[0]
            except:
                raise RuntimeError("No application context, no application registered")

        engines = app_engines[app]
        return engines[bind_key]

    def bind_context(
        self,
        bind_key: t.Optional[str] = None,
        execution_options: t.Optional[dict[str, t.Any]] = None,
        app: t.Optional[Quart] = None,
    ) -> BindContext:
        return BindContext(
            self, app, bind_key, execution_options=execution_options or {}
        )

    def _get_app_context(self, cache_fallback_enabled: bool = False):
        try:
            app_context = app_ctx._get_current_object()
        except RuntimeError:
            if (
                self._context_caching_enabled is False
                and cache_fallback_enabled is False
            ):
                raise
            app_context = self._last_app_ctx
        except:
            raise

        return app_context

    def get_session_scope(self, cache_fallback_enabled: bool = False):
        try:
            scope = self.session_scopefunc()
        except:
            app_ctx = self._get_app_context(
                cache_fallback_enabled=cache_fallback_enabled
            )
            scope = id(app_ctx)

        return scope

    def _call_for_binds(
        self, bind_key: str | None | list[str | None], op_name: str
    ) -> None:
        """Call a method on each metadata.

        :meta private:

        :param bind_key: A bind key or list of keys. Defaults to all binds.
        :param op_name: The name of the method to call.
        """
        if bind_key == "__all__":
            keys: list[str | None] = list(self.metadatas)
        elif bind_key is None or isinstance(bind_key, str):
            keys = [bind_key]
        else:
            keys = bind_key

        for key in keys:
            try:
                engine = self.engines[key]
            except KeyError:
                message = f"Bind key '{key}' is not in 'SQLALCHEMY_BINDS' config."

                if key is None:
                    message = f"'SQLALCHEMY_DATABASE_URI' config is not set. {message}"

                raise sa.exc.UnboundExecutionError(message) from None

            if hasattr(engine, "sync_engine"):
                engine = engine.sync_engine

            metadata = self.metadatas[key]
            getattr(metadata, op_name)(bind=engine)

    async def _async_call_for_binds(
        self,
        bind_key: str | None | list[str | None],
        op_name: str,
    ) -> None:
        engine = self.engines[bind_key]
        async with engine.begin() as conn:

            def sync_wrapper(_, db, bind_key, op_name):
                return db._call_for_binds(bind_key, op_name)

            await conn.run_sync(sync_wrapper, self, bind_key, op_name)

    async def async_create_all(
        self, bind_key: str | None | list[str | None] = "__all__"
    ) -> None:
        await self._async_call_for_binds(bind_key, "create_all")

    async def async_drop_all(
        self, bind_key: str | None | list[str | None] = "__all__"
    ) -> None:
        await self._async_call_for_binds(bind_key, "drop_all")

    async def async_reflect(
        self, bind_key: str | None | list[str | None] = "__all__"
    ) -> None:
        await self._async_call_for_binds(bind_key, "reflect")

    def create_all(self, bind_key: str | None | list[str | None] = "__all__") -> None:
        """Create tables that do not exist in the database by calling
        ``metadata.create_all()`` for all or some bind keys. This does not
        update existing tables, use a migration library for that.

        This requires that a Quart application context is active.

        :param bind_key: A bind key or list of keys to create the tables for. Defaults
            to all binds.
        """
        self._call_for_binds(bind_key, "create_all")

    def drop_all(self, bind_key: str | None | list[str | None] = "__all__") -> None:
        """Drop tables by calling ``metadata.drop_all()`` for all or some bind keys.

        This requires that a Quart application context is active.

        :param bind_key: A bind key or list of keys to drop the tables from. Defaults to
            all binds.
        """
        self._call_for_binds(bind_key, "drop_all")

    def reflect(self, bind_key: str | None | list[str | None] = "__all__") -> None:
        """Load table definitions from the database by calling ``metadata.reflect()``
        for all or some bind keys.

        This requires that a Quart application context is active.

        :param bind_key: A bind key or list of keys to reflect the tables from. Defaults
            to all binds.
        """
        self._call_for_binds(bind_key, "reflect")

    def _set_rel_query(self, kwargs: dict[str, t.Any]) -> None:
        """Apply the extension's :attr:`Query` class as the default for relationships
        and backrefs.

        :meta private:
        """
        kwargs.setdefault("query_class", self.Query)

        if "backref" in kwargs:
            backref = kwargs["backref"]

            if isinstance(backref, str):
                backref = (backref, {})

            backref[1].setdefault("query_class", self.Query)

    def relationship(
        self, *args: t.Any, **kwargs: t.Any
    ) -> sa.orm.RelationshipProperty[t.Any]:
        """A :func:`sqlalchemy.orm.relationship` that applies this extension's
        :attr:`Query` class for dynamic relationships and backrefs.
        """
        self._set_rel_query(kwargs)
        return sa.orm.relationship(*args, **kwargs)

    def dynamic_loader(
        self, argument: t.Any, **kwargs: t.Any
    ) -> sa.orm.RelationshipProperty[t.Any]:
        """A :func:`sqlalchemy.orm.dynamic_loader` that applies this extension's
        :attr:`Query` class for relationships and backrefs.
        """
        self._set_rel_query(kwargs)
        return sa.orm.dynamic_loader(argument, **kwargs)

    # def _relation(self, *args: t.Any, **kwargs: t.Any) -> sa.orm.RelationshipProperty[t.Any]:
    #     """A :func:`sqlalchemy.orm.relationship` that applies this extension's
    #     :attr:`Query` class for dynamic relationships and backrefs.

    #     SQLAlchemy 2.0 removes this name, use ``relationship`` instead.

    #     :meta private:

    #     .. versionchanged:: 3.0
    #         The :attr:`Query` class is set on ``backref``.
    #     """
    #     self._set_rel_query(kwargs)
    #     return sa.orm.relationship(*args, **kwargs)

    # relation = _relation

    def __getattr__(self, name: str) -> t.Any:
        if name.startswith("_"):
            raise AttributeError(name)

        for mod in (sa, sa.orm):
            if hasattr(mod, name):
                return getattr(mod, name)

        raise AttributeError(name)

    def __repr__(self) -> str:
        if not has_app_context():
            return f"<{type(self).__name__}>"

        message = f"{type(self).__name__} {self.engine.url}"

        if len(self.engines) > 1:
            message = f"{message} +{len(self.engines) - 1}"

        return f"<{message}>"


@dataclass
class BindContext:
    """
    The addition of engine_execution_options allows for applying specific execution_options to the
    engine used only in this context.   Examples of such usage include setting a different isolation
    level specific to this bind context.
    https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Engine.execution_options
    """

    db: InitVar[SQLAlchemy]
    app: InitVar[t.Optional[Quart]]
    bind_key: t.Optional[str]
    execution_options: dict[str, t.Any] = field(default_factory=dict)
    is_async: bool = field(init=False)
    engine: sa.Engine | sa.ext.asyncio.AsyncEngine = field(init=False)
    metadata: sa.MetaData = field(init=False, repr=False)
    connection: sa.Connection | sa.ext.asyncio.AsyncConnection = field(
        init=False, repr=False
    )
    session: sa.orm.scoped_session | sa.ext.asyncio.async_scoped_session = field(
        init=False, repr=False
    )

    def __post_init__(
        self,
        db: SQLAlchemy,
        app: t.Optional[Quart],
    ):
        self.engine = db.get_bind(self.bind_key, app=app).execution_options(
            **self.execution_options
        )
        self.is_async = self.engine.url.get_dialect().is_async
        self.metadata = db.metadatas[self.bind_key]
        session_options = db._session_options.copy()
        self.session = db._make_scoped_session(session_options, is_async=self.is_async)

    def __enter__(self):
        self.engine = t.cast(sa.Engine, self.engine)
        self.session = t.cast(sa.orm.scoped_session, self.session)

        self.engine.dispose(close=False)
        self.connection = self.engine.connect()
        self.session.configure(bind=self.connection)
        return self

    def __exit__(self, _, exc_val, __):
        if exc_val is not None:
            self.session.rollback()

        self.session.close()
        self.connection.close()
        self.session.remove()

        if exc_val is not None:
            raise exc_val

        self.engine.dispose(close=False)

    async def __aenter__(self):
        self.engine = t.cast(sa.ext.asyncio.AsyncEngine, self.engine)
        self.session = t.cast(sa.ext.asyncio.async_scoped_session, self.session)

        await self.engine.dispose(close=False)
        self.connection = await self.engine.connect()
        self.session.configure(bind=self.connection)
        return self

    async def __aexit__(self, _, exc_val, __):
        self.engine = t.cast(sa.ext.asyncio.AsyncEngine, self.engine)
        self.session = t.cast(sa.ext.asyncio.async_scoped_session, self.session)

        if exc_val is not None:
            await self.session.rollback()

        await self.session.close()
        await self.connection.close()  # type: ignore
        await self.engine.dispose()
        await self.session.remove()

        if exc_val is not None:
            raise exc_val
