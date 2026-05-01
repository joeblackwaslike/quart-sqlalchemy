import enum
import typing as t

import sqlalchemy

from .mixins import ComparableMixin, DynamicArgsMixin, ReprMixin, TableNameMixin

sa = sqlalchemy


class Base(DynamicArgsMixin, ReprMixin, ComparableMixin, TableNameMixin):
    __abstract__ = True

    type_annotation_map = {
        enum.StrEnum: sa.Enum(enum.StrEnum, native_enum=False, validate_strings=True),
        t.Literal: sa.Enum(enum.StrEnum, native_enum=False, validate_strings=True),
    }
