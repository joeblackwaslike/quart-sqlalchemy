from __future__ import annotations

import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column


sa = sqlalchemy


class DictMixin:
    __table__: sa.Table

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class IdentityMixin:
    id = sa.Column(sa.Integer, primary_key=True)


class SoftDeleteMixin:
    is_active: Mapped[bool] = mapped_column(default=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=sa.func.now())
    updated_at: Mapped[datetime] = mapped_column(default=sa.func.now(), onupdate=sa.func.now())


class VersionMixin:
    version_id: Mapped[int] = mapped_column(nullable=False)

    @sa.orm.declared_attr.directive
    def __mapper_args__(cls) -> dict[str, t.Any]:
        return {
            "version_id_col": cls.version_id,
            "eager_defaults": True,
        }


def softdelete_filter(execute_state: sa.orm.ORMExecuteState):
    if execute_state.is_select:
        execute_state.statement = execute_state.statement.options(
            sa.orm.with_loader_criteria(
                SoftDeleteMixin, lambda cls: hasattr(cls, "is_active"), include_aliases=True
            )
        )


# class TransientTodo(IdentityMixin, SoftDeleteMixin, db.Model):
#     name: Mapped[str] = mapped_column(default="Default")

# if not sa.event.contains(sa.orm.Session, "do_orm_execute", softdelete_filter):
#     sa.event.listen(sa.orm.Session, "do_orm_execute", softdelete_filter, propagate=True)

# sa.select(TransientTodo).with_loader_criteria(SoftDeleteMixin)
