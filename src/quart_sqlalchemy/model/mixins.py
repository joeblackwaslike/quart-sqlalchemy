from __future__ import annotations

import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
from sqlalchemy.orm import Mapped

from ..util import camel_to_snake_case


sa = sqlalchemy


class TableNameMixin:
    @sa.orm.declared_attr.directive
    def __tablename__(cls) -> str:
        return camel_to_snake_case(cls.__name__)


class ReprMixin:
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
    def __eq__(self, other):
        if type(self).__name__ != type(other).__name__:
            return False

        for key, column in sa.inspect(type(self)).columns.items():
            if column.primary_key:
                continue

            if not (getattr(self, key) == getattr(other, key)):
                return False
        return True


class TotalOrderMixin:
    def __lt__(self, other):
        if type(self).__name__ != type(other).__name__:
            return False

        for key, column in sa.inspect(type(self)).columns.items():
            if column.primary_key:
                continue

            if not (getattr(self, key) == getattr(other, key)):
                return False
        return True


class SimpleDictMixin:
    __abstract__ = True
    __table__: sa.Table

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class RecursiveDictMixin:
    __abstract__ = True

    def model_to_dict(
        self,
        obj: t.Optional[t.Any] = None,
        max_depth: int = 3,
        _children_seen: t.Optional[set] = None,
        _relations_seen: t.Optional[set] = None,
    ):
        """Convert model to python dict, with recursion.

        Args:
            obj (self):
                SQLAlchemy model inheriting from DeclarativeBase.
            max_depth (int):
                Maximum depth for recursion on relationships, defaults to 3.

        Returns:
            (dict) representation of the SQLAlchemy model.
        """
        if obj is None:
            obj = self
        if _children_seen is None:
            _children_seen = set()
        if _relations_seen is None:
            _relations_seen = set()

        mapper = sa.inspect(obj).mapper
        columns = [column.key for column in mapper.columns]

        def get_key_value(c):
            return (
                (c, getattr(obj, c).isoformat())
                if isinstance(getattr(obj, c), datetime)
                else (c, getattr(obj, c))
            )

        data = dict(map(get_key_value, columns))

        if max_depth > 0:
            for name, relation in mapper.relationships.items():
                if name in _relations_seen:
                    continue

                if relation.backref:
                    _relations_seen.add(name)

                relationship_children = getattr(obj, name)
                if relationship_children is not None:
                    if relation.uselist:
                        children = []
                        for child in (
                            c for c in relationship_children if c not in _children_seen
                        ):
                            _children_seen.add(child)
                            children.append(
                                self.model_to_dict(
                                    child,
                                    max_depth=max_depth - 1,
                                    _children_seen=_children_seen,
                                    _relations_seen=_relations_seen,
                                )
                            )
                        data[name] = children
                    else:
                        data[name] = self.model_to_dict(
                            relationship_children,
                            max_depth=max_depth - 1,
                            _children_seen=_children_seen,
                            _relations_seen=_relations_seen,
                        )

        return data


class IdentityMixin:
    id: Mapped[int] = sa.orm.mapped_column(
        sa.Identity(), primary_key=True, autoincrement=True
    )


class SoftDeleteMixin:
    """Use as a mixin in a class to opt-in to the soft-delete feature.

    At initialization time, the `soft_delete_filter` function below is registered on the
    `do_orm_execute` event.

    The expected effects of using this mixin are the addition of an is_active column by default, and

    Example:
        class User(db.Model, SoftDeleteMixin):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            email: Mapped[str] = sa.orm.mapped_column()

        db.create_all()

        u = User(email="joe@magic.link")
        db.session.add(u)
        db.session.commit()

        statement = select(User).where(name="joe@magic.link")

        # returns user
        result = db.session.execute(statement).scalars().one()

        # Mark inactive
        u.is_active = False
        db.session.add(u)
        db.session.commit()

        # User not found!
        result = db.session.execute(statement).scalars().one()

        # User found (when manually adding include_inactive execution option).
        # Now you can reactivate them if you like.
        result = db.session.execute(statement.execution_options(include_inactive=True)).scalars().one()

    see: https://docs.sqlalchemy.org/en/20/orm/versioning.html
    """

    __abstract__ = True

    is_active: Mapped[bool] = sa.orm.mapped_column(default=True)


class TimestampMixin:
    __abstract__ = True

    created_at: Mapped[datetime] = sa.orm.mapped_column(default=sa.func.now())
    updated_at: Mapped[datetime] = sa.orm.mapped_column(
        default=sa.func.now(), onupdate=sa.func.now()
    )


class VersionMixin:
    __abstract__ = True

    version_id: Mapped[int] = sa.orm.mapped_column(nullable=False)

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return dict(
            version_id_col=cls.version_id,
        )


class EagerDefaultsMixin:
    """
    https://docs.sqlalchemy.org/en/20/orm/mapping_api.html#sqlalchemy.orm.Mapper.params.eager_defaults
    """

    __abstract__ = True

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return dict(
            eager_defaults=True,
        )


def soft_delete_filter(execute_state: sa.orm.ORMExecuteState) -> None:
    if execute_state.is_select and not execute_state.execution_options.get(
        "include_inactive", False
    ):
        execute_state.statement = execute_state.statement.options(
            sa.orm.with_loader_criteria(
                SoftDeleteMixin,
                lambda cls: cls.is_active == sa.true(),
                include_aliases=True,
            )
        )


def setup_soft_delete_for_session(session: t.Type[sa.orm.Session]) -> None:
    if not sa.event.contains(
        session,
        "do_orm_execute",
        soft_delete_filter,
    ):
        sa.event.listen(
            session,
            "do_orm_execute",
            soft_delete_filter,
            propagate=True,
        )


def accumulate_mappings(class_, attribute) -> t.Dict[str, t.Any]:
    accumulated = {}
    for base_class in class_.__mro__[::-1]:
        if base_class is class_:
            continue
        args = getattr(base_class, attribute, {})
        accumulated.update(args)

    return accumulated


def accumulate_tuples_with_mapping(class_, attribute) -> t.Sequence[t.Any]:
    accumulated_map = {}
    accumulated_args = []

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
    def __mapper_args__(cls) -> t.Dict[str, t.Any]:
        return accumulate_mappings(cls, "__mapper_args__")

    @sa.orm.declared_attr.directive
    def __table_args__(cls) -> t.Sequence[t.Any]:
        return accumulate_tuples_with_mapping(cls, "__table_args__")
