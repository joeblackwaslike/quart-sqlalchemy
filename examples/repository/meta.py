from __future__ import annotations

import typing as t

from quart_sqlalchemy.model import SoftDeleteMixin
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.util import lazy_property


class TableMetadataMixin(t.Generic[EntityT]):
    model: type[EntityT]

    @lazy_property
    def table(self):
        return self.model.__table__

    @lazy_property
    def columns(self):
        return self.table

    @lazy_property
    def primary_keys(self):
        return set([column.name for column in self.model.__table__.primary_key.columns.values()])

    @lazy_property
    def required_keys(self):
        return set(
            [
                column.name
                for column in self.columns
                if not column.nullable and column.name not in self.primary_keys
            ]
        )

    @lazy_property
    def has_soft_delete(self):
        return issubclass(self.model, SoftDeleteMixin) or hasattr(self.model, "is_active")
