from __future__ import annotations

import dataclasses
import inspect
import typing as t
from time import perf_counter

import sqlalchemy as sa
import sqlalchemy.event
from quart import current_app
from quart import g
from quart import has_app_context


def get_recorded_queries() -> list[_QueryInfo]:
    """Get the list of recorded query information for the current session. Queries are
    recorded if the config :data:`.SQLALCHEMY_RECORD_QUERIES` is enabled.

    Each query info object has the following attributes:

    ``statement``
        The string of SQL generated by SQLAlchemy with parameter placeholders.
    ``parameters``
        The parameters sent with the SQL statement.
    ``start_time`` / ``end_time``
        Timing info about when the query started execution and when the results where
        returned. Accuracy and value depends on the operating system.
    ``duration``
        The time the query took in seconds.
    ``location``
        A string description of where in your application code the query was executed.
        This may not be possible to calculate, and the format is not stable.

    .. versionchanged:: 3.0
        Renamed from ``get_debug_queries``.

    .. versionchanged:: 3.0
        The info object is a dataclass instead of a tuple.

    .. versionchanged:: 3.0
        The info object attribute ``context`` is renamed to ``location``.

    .. versionchanged:: 3.0
        Not enabled automatically in debug or testing mode.
    """
    return g.get("_sqlalchemy_queries", [])  # type: ignore[no-any-return]


@dataclasses.dataclass
class _QueryInfo:
    """Information about an executed query. Returned by :func:`get_recorded_queries`.

    .. versionchanged:: 3.0
        Renamed from ``_DebugQueryTuple``.

    .. versionchanged:: 3.0
        Changed to a dataclass instead of a tuple.

    .. versionchanged:: 3.0
        ``context`` is renamed to ``location``.
    """

    statement: str | None
    parameters: t.Any
    start_time: float
    end_time: float
    location: str

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


def _listen(engine: sa.engine.Engine) -> None:
    sa.event.listen(engine, "before_cursor_execute", _record_start, named=True)
    sa.event.listen(engine, "after_cursor_execute", _record_end, named=True)


def _record_start(context: sa.engine.ExecutionContext, **kwargs: t.Any) -> None:
    if not has_app_context():
        return

    context._fsa_start_time = perf_counter()  # type: ignore[attr-defined]


def _record_end(context: sa.engine.ExecutionContext, **kwargs: t.Any) -> None:
    if not has_app_context():
        return

    if "_sqlalchemy_queries" not in g:
        g._sqlalchemy_queries = []

    import_top = current_app.import_name.partition(".")[0]
    import_dot = f"{import_top}."
    frame = inspect.currentframe()

    while frame:
        name = frame.f_globals.get("__name__")

        if name and (name == import_top or name.startswith(import_dot)):
            code = frame.f_code
            location = f"{code.co_filename}:{frame.f_lineno} ({code.co_name})"
            break

        frame = frame.f_back
    else:
        location = "<unknown>"

    g._sqlalchemy_queries.append(
        _QueryInfo(
            statement=context.statement,
            parameters=context.parameters,
            start_time=context._fsa_start_time,  # type: ignore[attr-defined]
            end_time=perf_counter(),
            location=location,
        )
    )