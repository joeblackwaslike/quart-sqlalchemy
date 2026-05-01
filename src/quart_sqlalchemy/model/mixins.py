import logging
import platform
import typing as t
from datetime import UTC, datetime

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
from packaging.version import Version
from sqlalchemy.orm import Mapped

from ..util import camel_to_snake_case

if Version(platform.python_version()) < Version("3.14"):
    import uuid_utils.compat as uuid
else:
    import uuid

sa = sqlalchemy

logger = logging.getLogger(__name__)


class TableNameMixin:
    """Automatically generates table names from class names.

    Converts CamelCase class names to snake_case table names.
    Skips inherited tables to avoid conflicts.

    Example:
        >>> class UserProfile(db.Model, TableNameMixin):
        ...     pass
        >>> UserProfile.__tablename__
        'user_profile'
    """

    @sa.orm.declared_attr.directive
    def __tablename__(cls) -> str | None:
        if sa.orm.has_inherited_table(cls):  # type: ignore[arg-type]
            return None
        return camel_to_snake_case(cls.__name__)  # type: ignore[attr-defined]


class ReprMixin:
    """Provides informative __repr__ for model instances.

    Shows primary key values and instance state (transient/pending/persistent).

    Example:
        >>> user = User(id=1, username="alice")
        >>> repr(user)
        '<User 1>'
    """

    def __repr__(self) -> str:
        state = sa.inspect(self)
        if state is None:
            return super().__repr__()

        if state.transient:
            pk = f"(transient {id(self)})"
        elif state.pending:
            pk = f"(pending {id(self)})"
        else:
            pk = ", ".join(map(str, state.identity))

        return f"<{type(self).__name__} {pk}>"


class ComparableMixin:
    """Enables equality comparison for model instances.

    Compares all non-primary-key columns for equality.

    Example:
        >>> user1 = User(id=1, username="alice", email="alice@example.com")
        >>> user2 = User(id=2, username="alice", email="alice@example.com")
        >>> user1 == user2  # True (same data, different IDs)
        True
    """

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False

        state = sa.inspect(type(self))
        if state is None:
            return super().__eq__(other)

        for key, column in state.columns.items():
            if column.primary_key:
                continue

            if not (getattr(self, key) == getattr(other, key)):
                return False
        return True


class TotalOrderMixin:
    def __lt__(self, other: object) -> bool:
        if not isinstance(other, type(self)):
            return False

        state = sa.inspect(type(self))
        if state is None:
            return NotImplemented

        for key, column in state.columns.items():
            if column.primary_key:
                continue

            if not (getattr(self, key) == getattr(other, key)):
                return False
        return True


class SimpleDictMixin:
    __abstract__ = True
    __table__: sa.Table

    def model_to_dict(self) -> dict[str, t.Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class RecursiveDictMixin:
    """Converts model instances to nested dictionaries with cycle detection.

    Safely traverses relationships up to a maximum depth, preventing infinite
    recursion and memory exhaustion on circular references.

    Example:
        >>> class User(db.Model, RecursiveDictMixin):
        ...     id: Mapped[int] = mapped_column(primary_key=True)
        ...     posts: Mapped[list["Post"]] = relationship(back_populates="user")
        >>>
        >>> user = User(id=1)
        >>> user.model_to_dict(max_depth=2)
        {'id': 1, 'posts': [{'id': 1, 'user_id': 1, ...}]}
    """

    __abstract__ = True

    # Maximum allowed depth to prevent abuse
    _MAX_SAFE_DEPTH = 5

    def model_to_dict(
        self,
        obj: t.Any | None = None,
        max_depth: int = 2,
        _children_seen: set[int] | None = None,
        _relations_seen: set[str] | None = None,
        _current_depth: int = 0,
    ) -> dict[str, t.Any]:
        """Convert model to python dict with safe recursion.

        Args:
            obj: SQLAlchemy model instance (defaults to self)
            max_depth: Maximum relationship depth (default: 2, max: 5)
            _children_seen: Internal - tracks visited objects by id()
            _relations_seen: Internal - tracks visited relationship names
            _current_depth: Internal - current recursion depth

        Returns:
            Dictionary representation of the model with nested relationships

        Raises:
            ValueError: If max_depth exceeds safety limit

        Warning:
            Deep recursion (max_depth > 3) may cause performance issues
            with large object graphs.
        """
        # Validate max_depth
        if max_depth > self._MAX_SAFE_DEPTH:
            raise ValueError(
                f"max_depth cannot exceed {self._MAX_SAFE_DEPTH} for safety. Got: {max_depth}"
            )

        # Initialize tracking sets on first call
        if obj is None:
            obj = self
        if _children_seen is None:
            _children_seen = set()
        if _relations_seen is None:
            _relations_seen = set()

        # Check for circular reference by object identity
        obj_id = id(obj)
        if obj_id in _children_seen:
            return {"_circular_ref": True, "_type": type(obj).__name__}

        # Check current depth
        if _current_depth > max_depth:
            return {"_truncated": True, "_type": type(obj).__name__}

        # Mark this object as visited
        _children_seen.add(obj_id)

        # Inspect the SQLAlchemy model
        state = sa.inspect(obj)
        if state is None:
            return {}

        mapper = state.mapper
        columns = [column.key for column in mapper.columns]

        def get_key_value(c: str) -> tuple[str, t.Any]:
            value = getattr(obj, c)
            # Convert datetime to ISO format string
            if isinstance(value, datetime):
                return (c, value.isoformat())
            return (c, value)

        # Build base dictionary with column values
        data = dict(map(get_key_value, columns))

        # Only recurse if we haven't hit max depth
        if _current_depth < max_depth:
            for name, relation in mapper.relationships.items():
                # Skip if we've already processed this relationship
                if name in _relations_seen:
                    continue

                # Mark backref relationships to avoid ping-ponging
                if relation.backref:
                    _relations_seen.add(name)

                try:
                    relationship_children = getattr(obj, name)
                except Exception:
                    # Skip relationships that fail to load
                    data[name] = {"_error": "Failed to load relationship"}
                    continue

                if relationship_children is not None:
                    if relation.uselist:
                        # Handle one-to-many / many-to-many
                        children = []
                        for child in relationship_children:
                            child_id = id(child)
                            # Skip if we've seen this child before
                            if child_id not in _children_seen:
                                children.append(
                                    self.model_to_dict(
                                        child,
                                        max_depth=max_depth,
                                        _children_seen=_children_seen,
                                        _relations_seen=_relations_seen.copy(),
                                        _current_depth=_current_depth + 1,
                                    )
                                )
                        data[name] = children
                    else:
                        # Handle many-to-one / one-to-one
                        child_id = id(relationship_children)
                        if child_id not in _children_seen:
                            data[name] = self.model_to_dict(
                                relationship_children,
                                max_depth=max_depth,
                                _children_seen=_children_seen,
                                _relations_seen=_relations_seen.copy(),
                                _current_depth=_current_depth + 1,
                            )
                        else:
                            data[name] = {
                                "_circular_ref": True,
                                "_type": type(relationship_children).__name__,
                            }

        return data


class IntIdMixin:
    id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)


class UuidIdMixin:
    id: Mapped[uuid.UUID] = sa.orm.mapped_column(primary_key=True, default=uuid.uuid7)


class SoftDeleteMixin:
    """Use as a mixin in a class to opt-in to the soft-delete feature.

    At initialization time, the `soft_delete_filter` function below is registered on the
    `do_orm_execute` event.

    The expected effects of using this mixin are the addition of an is_active column by default, and

    Example:
        class User(db.Model, SoftDeleteMixin):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            email: Mapped[str]

        db.create_all()

        u = User(email="me@joeblack.nyc")
        db.session.add(u)
        db.session.commit()

        statement = select(User).where(name="me@joeblack.nyc")

        # returns user
        result = db.session.scalars(statement).one()

        # Mark inactive
        u.soft_delete()
        db.session.add(u)
        db.session.commit()

        # User not found!
        result = db.session.scalars(statement).one()

        # User found (when manually adding `include_soft_deleted` execution option).
        # Now you can reactivate them if you like.
        result = db.session.scalars(statement.execution_options(include_soft_deleted=True)).one()

    see:
    """

    __abstract__ = True

    deleted_at: Mapped[datetime | None] = sa.orm.mapped_column(default=None)

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(UTC)

    def soft_undelete(self) -> None:
        self.deleted_at = None


def utc_now() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    __abstract__ = True

    created_at: Mapped[datetime] = sa.orm.mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = sa.orm.mapped_column(default=utc_now, onupdate=utc_now)


class VersionMixin:
    """see: https://docs.sqlalchemy.org/en/20/orm/versioning.html#mapper-version-counter"""

    __abstract__ = True

    version_id: Mapped[int]

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return dict(
            version_id_col=cls.version_id,
        )


class EagerDefaultsMixin:
    """https://docs.sqlalchemy.org/en/20/orm/mapping_api.html#sqlalchemy.orm.Mapper.params.eager_defaults"""

    __abstract__ = True

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return dict(
            eager_defaults=True,
        )


def soft_delete_filter(execute_state: sa.orm.ORMExecuteState) -> None:
    """Event listener that filters out soft-deleted records from SELECT queries.

    Automatically adds a WHERE clause to exclude records where deleted_at IS NOT NULL,
    unless the query explicitly sets the 'include_soft_deleted' execution option.

    Args:
        execute_state: SQLAlchemy ORM execution state object

    Note:
        This function is designed to be registered as a 'do_orm_execute' event listener.
        Use setup_soft_delete_for_session() to register it safely.

    Example:
        >>> # Without include_soft_deleted, deleted records are filtered
        >>> users = session.scalars(select(User)).all()
        >>>
        >>> # With include_soft_deleted=True, deleted records are included
        >>> all_users = session.scalars(
        ...     select(User).execution_options(include_soft_deleted=True)
        ... ).all()
    """
    # Only apply filter to SELECT statements
    if not execute_state.is_select:
        return

    # Skip if explicitly requesting soft-deleted records
    if execute_state.execution_options.get("include_soft_deleted", False):
        return

    try:
        # Apply loader criteria to filter out soft-deleted records
        execute_state.statement = execute_state.statement.options(
            sa.orm.with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.deleted_at.is_(None),
                include_aliases=True,
            )
        )
    except (AttributeError, TypeError) as e:
        # Handle cases where:
        # - Statement doesn't support options() (non-select statements that pass is_select)
        # - deleted_at attribute is missing or has wrong type
        # - cls is not a valid SQLAlchemy model
        # Log the error but don't fail the query
        logger.warning(
            "Failed to apply soft delete filter to query: %s. "
            "Query will execute without soft delete filtering.",
            e,
            exc_info=True,
        )
    except Exception as e:
        # Catch any other unexpected errors to prevent breaking queries
        logger.exception(
            "Unexpected error in soft_delete_filter: %s. "
            "Query will execute without soft delete filtering.",
            e,
        )


def setup_soft_delete_for_session(session: type[sa.orm.Session]) -> None:
    """Register the soft delete filter event listener on a session class.

    Idempotently attaches the soft_delete_filter to the 'do_orm_execute' event,
    ensuring it only gets registered once even if called multiple times.

    Args:
        session: SQLAlchemy Session class (not instance) to configure

    Note:
        The event listener is registered with propagate=True, so it will apply
        to all sessions created from this session class or its subclasses.

    Example:
        >>> from sqlalchemy.orm import Session
        >>> setup_soft_delete_for_session(Session)
        >>>
        >>> # Now all queries will automatically filter soft-deleted records
        >>> with Session(engine) as session:
        ...     users = session.scalars(select(User)).all()
    """
    if not sa.event.contains(session, "do_orm_execute", soft_delete_filter):
        sa.event.listen(session, "do_orm_execute", soft_delete_filter, propagate=True)


def accumulate_mappings(class_: type[t.Any], attribute: str) -> dict[str, t.Any]:
    accumulated: dict[str, t.Any] = {}
    for base_class in class_.__mro__[::-1]:
        if base_class is class_:
            continue
        args = getattr(base_class, attribute, {})
        accumulated.update(args)

    return accumulated


def accumulate_tuples_with_mapping(class_: type[t.Any], attribute: str) -> t.Sequence[t.Any]:
    accumulated_map: dict[str, t.Any] = {}
    accumulated_args: list[t.Any] = []

    for base_class in class_.__mro__[::-1]:
        if base_class is class_:
            continue
        args = getattr(base_class, attribute, ())
        for arg in args:
            if isinstance(arg, t.Mapping):
                accumulated_map.update(arg)
            else:
                accumulated_args.append(arg)

    if accumulated_map:
        accumulated_args.append(accumulated_map)
    return tuple(accumulated_args)


class DynamicArgsMixin:
    __abstract__ = True

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return accumulate_mappings(cls, "__mapper_args__")  # type: ignore[arg-type]

    @sa.orm.declared_attr.directive
    def __table_args__(cls) -> t.Sequence[t.Any]:
        return accumulate_tuples_with_mapping(cls, "__table_args__")  # type: ignore[arg-type]
