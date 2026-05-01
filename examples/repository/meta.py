import typing as t
from functools import cached_property

from quart_sqlalchemy.model import SoftDeleteMixin
from quart_sqlalchemy.types import EntityT


class TableMetadataMixin(t.Generic[EntityT]):
    model: type[EntityT]

    @cached_property
    def table(self):
        return self.model.__table__

    @cached_property
    def columns(self):
        return self.table

    @cached_property
    def primary_keys(self):
        return set([column.name for column in self.model.__table__.primary_key.columns.values()])

    @cached_property
    def required_keys(self):
        return {
            column.name
            for column in self.columns
            if not column.nullable and column.name not in self.primary_keys
        }

    @cached_property
    def has_soft_delete(self):
        return issubclass(self.model, SoftDeleteMixin) or hasattr(self.model, "deleted_at")
