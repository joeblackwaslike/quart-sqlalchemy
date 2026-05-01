import json
import os
import types
import typing as t

import sqlalchemy
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm.session import JoinTransactionMode
from sqlalchemy.sql.compiler import Compiled

from .model import Base
from .types import (
    BoundParamStyle,
    DMLStrategy,
    SessionBind,
    SessionBindKey,
    SynchronizeSession,
    TransactionIsolationLevel,
)

sa = sqlalchemy


def validate_dialect[T: BaseModel](
    config: T,
    kind: t.Literal["sync", "async"],
) -> T:
    engine = config.engine  # type: ignore[attr-defined]
    url = engine.url

    url = sa.make_url(url)
    is_async = url.get_dialect().is_async

    if any([
        kind == "sync" and is_async is True,
        kind == "async" and is_async is False,
    ]):
        raise ValueError(f"Async dialect required for {type(config).__name__}")

    return config


class ConfigBase(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @classmethod
    def default(cls) -> t.Self:
        return cls()


class CoreExecutionOptions(ConfigBase):
    """https://docs.sqlalchemy.org/en/20/core/connections.html#sqlalchemy.engine.Connection.execution_options
    """

    isolation_level: TransactionIsolationLevel | None = None
    compiled_cache: dict[t.Any, Compiled] | None = Field(default_factory=dict)
    logging_token: str | None = None
    no_parameters: bool = False
    stream_results: bool = False
    max_row_buffer: int = 1000
    yield_per: int | None = None
    insertmanyvalues_page_size: int = 1000
    schema_translate_map: dict[str, str] | None = None


class ORMExecutionOptions(ConfigBase):
    """https://docs.sqlalchemy.org/en/20/orm/queryguide/api.html#orm-queryguide-execution-options
    """

    isolation_level: TransactionIsolationLevel | None = None
    stream_results: bool = False
    yield_per: int | None = None
    populate_existing: bool = False
    autoflush: bool = True
    identity_token: str | None = None
    synchronize_session: SynchronizeSession = "auto"
    dml_strategy: DMLStrategy = "auto"


class EngineConfig(ConfigBase):
    """https://docs.sqlalchemy.org/en/20/core/engines.html#sqlalchemy.create_engine
    """

    url: sa.URL | str = "sqlite://"
    echo: bool = False
    echo_pool: bool = False
    connect_args: dict[str, t.Any] = Field(default_factory=dict)
    execution_options: CoreExecutionOptions = Field(default_factory=CoreExecutionOptions)
    enable_from_linting: bool = True
    hide_parameters: bool = False
    insertmanyvalues_page_size: int = 1000
    isolation_level: TransactionIsolationLevel | None = None
    json_deserializer: t.Callable[[str], t.Any] = json.loads
    json_serializer: t.Callable[[t.Any], str] = json.dumps
    label_length: int | None = None
    logging_name: str | None = None
    max_identifier_length: int | None = None
    max_overflow: int = 10
    module: types.ModuleType | None = None
    paramstyle: BoundParamStyle | None = None
    pool: sa.Pool | None = None
    poolclass: type[sa.Pool] | None = None
    pool_logging_name: str | None = None
    pool_pre_ping: bool = False
    pool_size: int = 5
    pool_recycle: int = -1
    pool_reset_on_return: t.Literal["values", "rollback"] | None = None
    pool_timeout: int = 40
    pool_use_lifo: bool = False
    plugins: t.Sequence[str] = Field(default_factory=list)
    query_cache_size: int = 500
    user_insertmanyvalues: bool = True

    @classmethod
    def default(cls) -> t.Self:
        return cls(url="sqlite://")

    @model_validator(mode="after")
    def apply_driver_defaults(self) -> t.Self:
        url = sa.make_url(self.url)
        driver = url.drivername

        if driver.startswith("sqlite"):
            if url.database is None or url.database in {"", ":memory:"}:
                self.poolclass = sa.StaticPool
                self.connect_args["check_same_thread"] = False
            else:
                # the url might look like sqlite:///file:path?uri=true
                is_uri = bool(url.query.get("uri", False))
                mode = url.query.get("mode", "")

                if is_uri and mode == "memory":
                    return self

                db_str = url.database[5:] if is_uri else url.database
                if not os.path.isabs(db_str):
                    if is_uri:
                        db_str = f"file:{db_str}"

                    self.url = url.set(database=db_str)
        elif driver.startswith("mysql"):
            self.pool_pre_ping = True
            # set queue defaults only when using queue pool
            if self.poolclass is sa.QueuePool:
                self.pool_recycle = 7200

            if "charset" not in url.query:
                self.url = url.update_query_dict({"charset": "utf8mb4"})

        return self


class SessionOptions(ConfigBase):
    """https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.Session
    """

    autoflush: bool = True
    autobegin: bool = True
    expire_on_commit: bool = False
    bind: SessionBind | None = None
    binds: dict[SessionBindKey, SessionBind] | None = None
    twophase: bool = False
    info: dict[t.Any, t.Any] | None = None
    join_transaction_mode: JoinTransactionMode = "conditional_savepoint"


class SessionmakerOptions(SessionOptions):
    """https://docs.sqlalchemy.org/en/20/orm/session_api.html#sqlalchemy.orm.sessionmaker
    """

    class_: type[sa.orm.Session] = sa.orm.Session


class AsyncSessionOptions(SessionOptions):
    """https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.AsyncSession
    """

    sync_session_class: type[sa.orm.Session] = sa.orm.Session


class AsyncSessionmakerOptions(AsyncSessionOptions):
    """https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#sqlalchemy.ext.asyncio.async_sessionmaker
    """

    class_: type[sa.ext.asyncio.AsyncSession] = sa.ext.asyncio.AsyncSession


class BindConfig(ConfigBase):
    read_only: bool = False
    session: SessionmakerOptions = Field(default_factory=SessionmakerOptions.default)
    engine: EngineConfig = Field(default_factory=EngineConfig.default)

    @model_validator(mode="before")
    @classmethod
    def expand_url_shorthand(cls, data: t.Any) -> t.Any:
        if isinstance(data, dict) and "url" in data and "engine" not in data:
            data = dict(data)
            data["engine"] = {"url": data.pop("url")}
        return data

    @model_validator(mode="after")
    def validate_dialect(self) -> t.Self:
        return validate_dialect(self, "sync")


class AsyncBindConfig(BindConfig):
    session: AsyncSessionmakerOptions = Field(default_factory=AsyncSessionmakerOptions.default)  # type: ignore[assignment]

    @model_validator(mode="after")
    def validate_dialect(self) -> t.Self:
        return validate_dialect(self, "async")


def default() -> None:
    dict(default=dict())


class SQLAlchemyConfig(ConfigBase):
    _web_config_field_map = {
        "SQLALCHEMY_MODEL_CLASS": "model_class",
        "SQLALCHEMY_BINDS": "binds",
    }

    model_class: type[t.Any] = Base
    binds: dict[str, AsyncBindConfig | BindConfig] = Field(
        default_factory=lambda: dict(default=BindConfig())
    )

    @classmethod
    def from_framework(cls, values: dict[str, t.Any]) -> t.Self:
        key_map = cls._web_config_field_map
        return cls(**{key_map.get(key, key): val for key, val in values.items()})
