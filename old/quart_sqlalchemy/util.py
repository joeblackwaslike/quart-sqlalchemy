import os
import functools

import sqlalchemy
import sqlalchemy.orm
from sqlalchemy import event
from sqlalchemy.engine.url import make_url
from quart import _app_ctx_stack


def _sa_url_set(url, **kwargs):
    try:
        url = url.set(**kwargs)
    except AttributeError:
        # SQLAlchemy <= 1.3
        for key, value in kwargs.items():
            setattr(url, key, value)

    return url


def _sa_url_query_setdefault(url, **kwargs):
    query = dict(url.query)

    for key, value in kwargs.items():
        query.setdefault(key, value)

    return _sa_url_set(url, query=query)


def _make_table(db):
    def _make_table(*args, **kwargs):
        if len(args) > 1 and isinstance(args[1], db.Column):
            args = (args[0], db.metadata) + args[1:]
        info = kwargs.pop("info", None) or {}
        info.setdefault("bind_key", None)
        kwargs["info"] = info
        return sqlalchemy.Table(*args, **kwargs)

    return _make_table


def _set_default_query_class(d, cls):
    if "query_class" not in d:
        d["query_class"] = cls


def _wrap_with_default_query_class(fn, cls):
    @functools.wraps(fn)
    def newfn(*args, **kwargs):
        _set_default_query_class(kwargs, cls)
        if "backref" in kwargs:
            backref = kwargs["backref"]
            if isinstance(backref, str):
                backref = (backref, {})
            _set_default_query_class(backref[1], cls)
        return fn(*args, **kwargs)

    return newfn


def _include_sqlalchemy(obj, cls):
    for module in sqlalchemy, sqlalchemy.orm:
        for key in module.__all__:
            if not hasattr(obj, key):
                setattr(obj, key, getattr(module, key))
    # Note: obj.Table does not attempt to be a SQLAlchemy Table class.
    obj.Table = _make_table(obj)
    obj.relationship = _wrap_with_default_query_class(obj.relationship, cls)
    obj.relation = _wrap_with_default_query_class(obj.relation, cls)
    obj.dynamic_loader = _wrap_with_default_query_class(obj.dynamic_loader, cls)
    obj.event = event


def _record_queries(app):
    if app.debug:
        return True
    rq = app.config["SQLALCHEMY_RECORD_QUERIES"]
    if rq is not None:
        return rq
    return bool(app.config.get("TESTING"))


def get_state(app):
    """Gets the state for the application"""
    assert "sqlalchemy" in app.extensions, (
        "The sqlalchemy extension was not registered to the current "
        "application.  Please make sure to call init_app() first."
    )
    return app.extensions["sqlalchemy"]


def apply_driver_hacks(db_uri, root_path, options=None):
    """This method is called before engine creation and used to inject
    driver specific hacks into the options.  The `options` parameter is
    a dictionary of keyword arguments that will then be used to call
    the :func:`sqlalchemy.create_engine` function.

    The default implementation provides some defaults for things
    like pool sizes for MySQL and SQLite.

    .. versionchanged:: 3.0
        Change the default MySQL character set to "utf8mb4".

    .. versionchanged:: 2.5
        Returns ``(sa_url, options)``. SQLAlchemy 1.4 made the URL
        immutable, so any changes to it must now be passed back up
        to the original caller.
    """
    options = options or {}
    sa_url = make_url(db_uri)

    if sa_url.drivername.startswith("mysql"):
        sa_url = _sa_url_query_setdefault(sa_url, charset="utf8mb4")

        if sa_url.drivername != "mysql+gaerdbms":
            options.setdefault("pool_size", 10)
            options.setdefault("pool_recycle", 7200)
    elif sa_url.drivername == "sqlite":
        pool_size = options.get("pool_size")
        detected_in_memory = False
        if sa_url.database in (None, "", ":memory:"):
            detected_in_memory = True
            from sqlalchemy.pool import StaticPool

            options["poolclass"] = StaticPool
            if "connect_args" not in options:
                options["connect_args"] = {}
            options["connect_args"]["check_same_thread"] = False

            # we go to memory and the pool size was explicitly set
            # to 0 which is fail.  Let the user know that
            if pool_size == 0:
                raise RuntimeError(
                    "SQLite in memory database with an "
                    "empty queue not possible due to data "
                    "loss."
                )
        # if pool size is None or explicitly set to 0 we assume the
        # user did not want a queue for this sqlite connection and
        # hook in the null pool.
        elif not pool_size:
            from sqlalchemy.pool import NullPool

            options["poolclass"] = NullPool

        if not detected_in_memory and not os.path.isabs(sa_url.database):
            sa_url = _sa_url_set(
                sa_url, database=os.path.join(root_path, sa_url.database)
            )

    return sa_url, options


def ensure_db_path_exists(sa_url, root_path)
    # If the database path is not absolute, it's relative to the
    # app instance path, which might need to be created.
    if not os.path.isabs(sa_url.database):
        os.makedirs(root_path, exist_ok=True)
