from __future__ import annotations

import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from . import signals


sa = sqlalchemy

if t.TYPE_CHECKING:
    from .extension import SQLAlchemy


class DictMixin:
    __table__: sa.Table

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class IdentityMixin:
    id: Mapped[int] = sa.orm.mapped_column(primary_key=True)


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
    """

    is_active: Mapped[bool] = mapped_column(default=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(default=sa.func.now(), onupdate=sa.func.now())


class VersionMixin:
    """ """

    version_id: Mapped[int] = mapped_column(nullable=False)

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return {
            "version_id_col": cls.version_id,
        }


def soft_delete_filter(execute_state: sa.orm.ORMExecuteState):
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


@signals.after_app_initialized.connect
def setup_soft_delete_session_support(extension: SQLAlchemy, app: Quart):
    if not sa.event.contains(
        extension._session_class,
        "do_orm_execute",
        soft_delete_filter,
    ):
        sa.event.listen(
            extension._session_class,
            "do_orm_execute",
            soft_delete_filter,
            propagate=True,
        )
