from __future__ import annotations

import enum
import uuid

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
import typing_extensions as tx
from sqlalchemy_utils import JSONType

from .mixins import ComparableMixin
from .mixins import DynamicArgsMixin
from .mixins import EagerDefaultsMixin
from .mixins import RecursiveDictMixin
from .mixins import ReprMixin
from .mixins import TableNameMixin
from .mixins import TotalOrderMixin


sa = sqlalchemy

default_metadata_naming_convention = {
    "ix": "ix_%(column_0_label)s",  # INDEX
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",  # UNIQUE
    "ck": "ck_%(table_name)s_%(constraint_name)s",  # CHECK
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",  # FOREIGN KEY
    "pk": "pk_%(table_name)s",  # PRIMARY KEY
}

default_type_annotation_map = {
    enum.Enum: sa.Enum(enum.Enum, native_enum=False, validate_strings=True),
    tx.Literal: sa.Enum(enum.Enum, native_enum=False, validate_strings=True),
    uuid.UUID: sa.Uuid,
    dict: JSONType,
}


class BaseMixins(
    DynamicArgsMixin,
    EagerDefaultsMixin,
    ReprMixin,
    RecursiveDictMixin,
    TotalOrderMixin,
    ComparableMixin,
    TableNameMixin,
):
    __abstract__ = True
    __table__: sa.Table


class Base(BaseMixins, sa.orm.DeclarativeBase):
    __abstract__ = True
    metadata = sa.MetaData(naming_convention=default_metadata_naming_convention)
    type_annotation_map = default_type_annotation_map
