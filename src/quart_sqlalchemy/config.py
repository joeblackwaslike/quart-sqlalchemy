from __future__ import annotations

import os
import types
import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.sql.sqltypes
import sqlalchemy.util
import typing_extensions as tx
from pydantic import BaseModel
from pydantic import Field
from pydantic import root_validator
from sqlalchemy.orm.session import JoinTransactionMode
from sqlalchemy.sql.compiler import Compiled

from .model import Base
from .types import BoundParamStyle
from .types import DMLStrategy
from .types import Empty
from .types import EmptyType
from .types import SessionBind
from .types import SessionBindKey
from .types import SynchronizeSession
from .types import TransactionIsolationLevel


sa = sqlalchemy


def validate_dialect(
    config_class: BaseModel,
    values: t.Dict[str, t.Any],
    kind: tx.Literal["sync", "async"],
) -> t.Dict[str, t.Any]:
    try:
        engine = getattr(values, "engine")
    except AttributeError:
        engine = values.get("engine", {})

    try:
        url = getattr(engine, "url")
    except AttributeError:
        url = engine.get("url", "sqlite://")
    url = sa.make_url(url)
    is_async = url.get_dialect().is_async

    if any(
        [
            kind == "sync" and is_async is True,
            kind == "async" and is_async is False,
        ]
    ):
        raise ValueError(f"Async dialect required for {config_class.__name__}")

    return values


class ConfigBase(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    @root_validator
    def scrub_empty(cls, values):
        return {key: val for key, val in values.items() if val not in [Empty, {}]}


class CoreExecutionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection.execution_options
    """

    isolation_level: t.Union[TransactionIsolationLevel, EmptyType] = Empty
    compiled_cache: t.Union[t.Dict[t.Any, Compiled], None, EmptyType] = Empty
    logging_token: t.Union[str, None, EmptyType] = Empty
    no_parameters: t.Union[bool, EmptyType] = Empty
    stream_results: t.Union[bool, EmptyType] = Empty
    max_row_buffer: t.Union[int, EmptyType] = Empty
    yield_per: t.Union[int, None, EmptyType] = Empty
    insertmanyvalues_page_size: t.Union[int, EmptyType] = Empty
    schema_translate_map: t.Union[t.Dict[str, str], None, EmptyType] = Empty


class ORMExecutionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#orm-queryguide-execution-options
    """

    isolation_level: t.Union[TransactionIsolationLevel, EmptyType] = Empty
    stream_results: t.Union[bool, EmptyType] = Empty
    yield_per: t.Union[int, None, EmptyType] = Empty
    populate_existing: t.Union[bool, EmptyType] = Empty
    autoflush: t.Union[bool, EmptyType] = Empty
    identity_token: t.Union[str, None, EmptyType] = Empty
    synchronize_session: t.Union[SynchronizeSession, None, EmptyType] = Empty
    dml_strategy: t.Union[DMLStrategy, None, EmptyType] = Empty


# connect_args:
#   mysql:
#     connect_timeout:
#   postgres:
#     connect_timeout:


class EngineConfig(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine
    """

    url: t.Union[sa.URL, str, EmptyType] = Empty
    echo: t.Union[bool, EmptyType] = Empty
    echo_pool: t.Union[bool, EmptyType] = Empty
    connect_args: t.Union[t.Dict[str, t.Any], EmptyType] = Empty
    execution_options: CoreExecutionOptions = Field(default_factory=CoreExecutionOptions)
    enable_from_linting: t.Union[bool, EmptyType] = Empty
    hide_parameters: t.Union[bool, EmptyType] = Empty
    insertmanyvalues_page_size: t.Union[int, EmptyType] = Empty
    isolation_level: t.Union[TransactionIsolationLevel, EmptyType] = Empty
    json_deserializer: t.Union[t.Callable[[str], t.Any], EmptyType] = Empty
    json_serializer: t.Union[t.Callable[[t.Any], str], EmptyType] = Empty
    label_length: t.Union[int, None, EmptyType] = Empty
    logging_name: t.Union[str, None, EmptyType] = Empty
    max_identifier_length: t.Union[int, None, EmptyType] = Empty
    max_overflow: t.Union[int, EmptyType] = Empty
    module: t.Union[types.ModuleType, None, EmptyType] = Empty
    paramstyle: t.Union[BoundParamStyle, None, EmptyType] = Empty
    pool: t.Union[sa.Pool, None, EmptyType] = Empty
    poolclass: t.Union[t.Type[sa.Pool], None, EmptyType] = Empty
    pool_logging_name: t.Union[str, None, EmptyType] = Empty
    pool_pre_ping: t.Union[bool, EmptyType] = Empty
    pool_size: t.Union[int, EmptyType] = Empty
    pool_recycle: t.Union[int, EmptyType] = Empty
    pool_reset_on_return: t.Union[tx.Literal["values", "rollback"], None, EmptyType] = Empty
    pool_timeout: t.Union[int, EmptyType] = Empty
    pool_use_lifo: t.Union[bool, EmptyType] = Empty
    plugins: t.Union[t.Sequence[str], EmptyType] = Empty
    query_cache_size: t.Union[int, EmptyType] = Empty
    user_insertmanyvalues: t.Union[bool, EmptyType] = Empty

    @root_validator
    def scrub_execution_options(cls, values):
        if "execution_options" in values:
            execute_options = values["execution_options"].dict(exclude_defaults=True)
            if execute_options:
                values["execution_options"] = execute_options
        return values

    @root_validator
    def set_defaults(cls, values):
        values.setdefault("url", "sqlite://")
        return values

    @root_validator
    def apply_driver_defaults(cls, values):
        # values["execution_options"] = values["execution_options"].dict(exclude_defaults=True)
        # values = {key: val for key, val in values.items() if val not in [Empty, {}]}
        # values.setdefault("url", "sqlite://")

        url = sa.make_url(values["url"])
        driver = url.drivername

        if driver.startswith("sqlite"):
            if url.database is None or url.database in {"", ":memory:"}:
                values["poolclass"] = sa.StaticPool

                if "connect_args" not in values:
                    values["connect_args"] = {}

                values["connect_args"]["check_same_thread"] = False
            else:
                # the url might look like sqlite:///file:path?uri=true
                is_uri = bool(url.query.get("uri", False))
                mode = url.query.get("mode", "")

                if is_uri and mode == "memory":
                    return values

                db_str = url.database[5:] if is_uri else url.database
                if not os.path.isabs(db_str):
                    if is_uri:
                        db_str = f"file:{db_str}"

                    values["url"] = url.set(database=db_str)
        elif driver.startswith("mysql"):
            values.setdefault("pool_pre_ping", True)
            # set queue defaults only when using queue pool
            if "pool_class" not in values or values["pool_class"] is sa.QueuePool:
                values.setdefault("pool_recycle", 7200)

            if "charset" not in url.query:
                values["url"] = url.update_query_dict({"charset": "utf8mb4"})

        return values


class AsyncEngineConfig(EngineConfig):
    @root_validator
    def set_defaults(cls, values):
        values.setdefault("url", "sqlite+aiosqlite://")
        return values


class SessionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session
    """

    autoflush: t.Union[bool, EmptyType] = Empty
    autobegin: t.Union[bool, EmptyType] = Empty
    expire_on_commit: t.Union[bool, EmptyType] = Empty
    bind: t.Union[SessionBind, None, EmptyType] = Empty
    binds: t.Union[t.Dict[SessionBindKey, SessionBind], None, EmptyType] = Empty
    twophase: t.Union[bool, EmptyType] = Empty
    info: t.Union[t.Dict[t.Any, t.Any], None, EmptyType] = Empty
    join_transaction_mode: t.Union[JoinTransactionMode, EmptyType] = Empty

    @root_validator
    def set_defaults(cls, values):
        values.setdefault("expire_on_commit", False)
        return values


class SessionmakerOptions(SessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.sessionmaker
    """

    class_: t.Union[t.Type[sa.orm.Session], EmptyType] = Empty


class AsyncSessionOptions(SessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession
    """

    sync_session_class: t.Union[t.Type[sa.orm.Session], EmptyType] = Empty


class AsyncSessionmakerOptions(AsyncSessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.async_sessionmaker
    """

    class_: t.Union[t.Type[sa.ext.asyncio.AsyncSession], EmptyType] = Empty


class BindConfig(ConfigBase):
    read_only: bool = False
    session: SessionmakerOptions = Field(default_factory=SessionmakerOptions)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    track_instance: bool = False

    @root_validator
    def validate_dialect(cls, values):
        return validate_dialect(cls, values, "sync")


class AsyncBindConfig(BindConfig):
    session: AsyncSessionmakerOptions = Field(default_factory=AsyncSessionmakerOptions)
    engine: AsyncEngineConfig = Field(default_factory=AsyncEngineConfig)

    @root_validator
    def validate_dialect(cls, values):
        return validate_dialect(cls, values, "async")


class SQLAlchemyConfig(ConfigBase):
    base_class: t.Type[t.Any] = Base
    binds: t.Dict[str, t.Union[BindConfig, AsyncBindConfig]] = Field(default_factory=dict)

    @root_validator
    def set_default_bind(cls, values):
        values.setdefault("binds", dict(default=BindConfig()))
        return values

    @classmethod
    def from_framework(cls, framework_config):
        config = framework_config.get_namespace("SQLALCHEMY_")
        return cls.parse_obj(config or {})
