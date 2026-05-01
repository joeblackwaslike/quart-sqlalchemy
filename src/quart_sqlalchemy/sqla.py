import typing as t

import sqlalchemy
import sqlalchemy.orm

from .bind import AsyncBind, Bind
from .config import AsyncBindConfig, SQLAlchemyConfig

sa = sqlalchemy


class SQLAlchemy:
    """Framework-agnostic SQLAlchemy integration.

    Core class that manages database binds, declarative base, and metadata.
    Supports multiple named binds for multi-database applications.

    Attributes:
        config: SQLAlchemy configuration
        binds: Dictionary of named database binds
        Base: Declarative base class for ORM models

    Example:
        >>> from quart_sqlalchemy import SQLAlchemy, SQLAlchemyConfig
        >>> config = SQLAlchemyConfig()
        >>> db = SQLAlchemy(config)
        >>>
        >>> class User(db.Base):
        ...     __tablename__ = 'users'
        ...     id: Mapped[int] = mapped_column(primary_key=True)
        ...     username: Mapped[str]
        >>>
        >>> db.create_all()
    """

    config: SQLAlchemyConfig
    binds: dict[str, Bind | AsyncBind]
    Base: type[sa.orm.DeclarativeBase]

    def __init__(self, config: SQLAlchemyConfig, initialize: bool = True) -> None:
        """Initialize SQLAlchemy with configuration.

        Args:
            config: SQLAlchemy configuration
            initialize: Whether to initialize immediately (default: True)
        """
        self.config = config

        if initialize:
            self.initialize()

    def initialize(self) -> None:
        """Initialize the declarative base and database binds.

        Creates the Base class and initializes all configured binds.
        """
        if issubclass(self.config.model_class, sa.orm.DeclarativeBase):
            self.Base = self.config.model_class
        else:
            model_class = self.config.model_class

            class Base(model_class, sa.orm.DeclarativeBase):  # type: ignore[misc,valid-type]
                pass

            self.Base = Base

        self.binds = {}
        for name, bind_config in self.config.binds.items():
            is_async = isinstance(bind_config, AsyncBindConfig)
            if is_async:
                self.binds[name] = AsyncBind(bind_config, self.metadata)
            else:
                self.binds[name] = Bind(bind_config, self.metadata)

    @classmethod
    def default(cls) -> "SQLAlchemy":
        return cls(SQLAlchemyConfig())

    @property
    def bind(self) -> Bind | AsyncBind:
        """Get the default database bind.

        Returns:
            The default bind instance
        """
        return self.get_bind()

    @property
    def metadata(self) -> sa.MetaData:
        """Get the SQLAlchemy metadata registry.

        Returns:
            Metadata containing all table definitions
        """
        return self.Base.metadata

    def get_bind(self, bind: str = "default") -> Bind | AsyncBind:
        """Get a named database bind.

        Args:
            bind: Bind name (default: "default")

        Returns:
            The requested bind instance

        Raises:
            KeyError: If bind name not found
        """
        return self.binds[bind]

    def create_all(self, bind: str = "default") -> None | t.Awaitable[None]:
        """Create all tables in the specified bind.

        For sync binds, this executes immediately and returns None.
        For async binds, this returns an awaitable that must be awaited.

        Args:
            bind: Bind name (default: "default")

        Returns:
            None for sync binds, Awaitable[None] for async binds

        Example:
            >>> # Sync usage
            >>> db.create_all()
            >>>
            >>> # Async usage
            >>> await db.create_all()
        """
        result = self.binds[bind].create_all()
        return result

    def drop_all(self, bind: str = "default") -> None | t.Awaitable[None]:
        """Drop all tables in the specified bind.

        For sync binds, this executes immediately and returns None.
        For async binds, this returns an awaitable that must be awaited.

        Args:
            bind: Bind name (default: "default")

        Returns:
            None for sync binds, Awaitable[None] for async binds

        Example:
            >>> # Sync usage
            >>> db.drop_all()
            >>>
            >>> # Async usage
            >>> await db.drop_all()
        """
        result = self.binds[bind].drop_all()
        return result

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.bind.engine.url}>"
