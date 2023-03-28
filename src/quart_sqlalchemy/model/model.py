from __future__ import annotations

import enum

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
import typing_extensions as tx

from .mixins import ComparableMixin
from .mixins import DynamicArgsMixin
from .mixins import ReprMixin
from .mixins import TableNameMixin


sa = sqlalchemy


class Base(DynamicArgsMixin, ReprMixin, ComparableMixin, TableNameMixin):
    __abstract__ = True

    type_annotation_map = {
        enum.Enum: sa.Enum(enum.Enum, native_enum=False, validate_strings=True),
        tx.Literal: sa.Enum(enum.Enum, native_enum=False, validate_strings=True),
    }
