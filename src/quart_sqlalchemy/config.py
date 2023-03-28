from __future__ import annotations

import json
import os
import types
import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
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

    @classmethod
    def default(cls):
        return cls()


class CoreExecutionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection.execution_options
    """

    isolation_level: t.Optional[TransactionIsolationLevel] = None
    compiled_cache: t.Optional[t.Dict[t.Any, Compiled]] = Field(default_factory=dict)
    logging_token: t.Optional[str] = None
    no_parameters: bool = False
    stream_results: bool = False
    max_row_buffer: int = 1000
    yield_per: t.Optional[int] = None
    insertmanyvalues_page_size: int = 1000
    schema_translate_map: t.Optional[t.Dict[str, str]] = None


class ORMExecutionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#orm-queryguide-execution-options
    """

    isolation_level: t.Optional[TransactionIsolationLevel] = None
    stream_results: bool = False
    yield_per: t.Optional[int] = None
    populate_existing: bool = False
    autoflush: bool = True
    identity_token: t.Optional[str] = None
    synchronize_session: SynchronizeSession = "auto"
    dml_strategy: DMLStrategy = "auto"


class EngineConfig(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine
    """

    url: t.Union[sa.URL, str] = "sqlite://"
    echo: bool = False
    echo_pool: bool = False
    connect_args: t.Dict[str, t.Any] = Field(default_factory=dict)
    execution_options: CoreExecutionOptions = Field(default_factory=CoreExecutionOptions)
    enable_from_linting: bool = True
    hide_parameters: bool = False
    insertmanyvalues_page_size: int = 1000
    isolation_level: t.Optional[TransactionIsolationLevel] = None
    json_deserializer: t.Callable[[str], t.Any] = json.loads
    json_serializer: t.Callable[[t.Any], str] = json.dumps
    label_length: t.Optional[int] = None
    logging_name: t.Optional[str] = None
    max_identifier_length: t.Optional[int] = None
    max_overflow: int = 10
    module: t.Optional[types.ModuleType] = None
    paramstyle: t.Optional[BoundParamStyle] = None
    pool: t.Optional[sa.Pool] = None
    poolclass: t.Optional[t.Type[sa.Pool]] = None
    pool_logging_name: t.Optional[str] = None
    pool_pre_ping: bool = False
    pool_size: int = 5
    pool_recycle: int = -1
    pool_reset_on_return: t.Optional[tx.Literal["values", "rollback"]] = None
    pool_timeout: int = 40
    pool_use_lifo: bool = False
    plugins: t.Sequence[str] = Field(default_factory=list)
    query_cache_size: int = 500
    user_insertmanyvalues: bool = True

    @classmethod
    def default(cls):
        return cls(url="sqlite://")

    @root_validator
    def apply_driver_defaults(cls, values):
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


class SessionOptions(ConfigBase):
    """
    https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session
    """

    autoflush: bool = True
    autobegin: bool = True
    expire_on_commit: bool = False
    bind: t.Optional[SessionBind] = None
    binds: t.Optional[t.Dict[SessionBindKey, SessionBind]] = None
    twophase: bool = False
    info: t.Optional[t.Dict[t.Any, t.Any]] = None
    join_transaction_mode: JoinTransactionMode = "conditional_savepoint"


class SessionmakerOptions(SessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.sessionmaker
    """

    class_: t.Type[sa.orm.Session] = sa.orm.Session


class AsyncSessionOptions(SessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession
    """

    sync_session_class: t.Type[sa.orm.Session] = sa.orm.Session


class AsyncSessionmakerOptions(AsyncSessionOptions):
    """
    https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.async_sessionmaker
    """

    class_: t.Type[sa.ext.asyncio.AsyncSession] = sa.ext.asyncio.AsyncSession


class BindConfig(ConfigBase):
    read_only: bool = False
    session: SessionmakerOptions = Field(default_factory=SessionmakerOptions.default)
    engine: EngineConfig = Field(default_factory=EngineConfig.default)

    @root_validator
    def validate_dialect(cls, values):
        return validate_dialect(cls, values, "sync")


class AsyncBindConfig(BindConfig):
    session: AsyncSessionmakerOptions = Field(default_factory=AsyncSessionmakerOptions.default)

    @root_validator
    def validate_dialect(cls, values):
        return validate_dialect(cls, values, "async")


def default():
    dict(default=dict())


class SQLAlchemyConfig(ConfigBase):
    class Meta:
        web_config_field_map = {
            "SQLALCHEMY_MODEL_CLASS": "model_class",
            "SQLALCHEMY_BINDS": "binds",
        }

    model_class: t.Type[t.Any] = Base
    binds: t.Dict[str, t.Union[AsyncBindConfig, BindConfig]] = Field(
        default_factory=lambda: dict(default=BindConfig())
    )

    @classmethod
    def from_framework(cls, values: t.Dict[str, t.Any]):
        key_map = cls.Meta.web_config_field_map
        return cls(**{key_map.get(key, key): val for key, val in values.items()})
