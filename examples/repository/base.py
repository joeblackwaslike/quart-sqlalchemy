from __future__ import annotations

import typing as t
from abc import ABCMeta
from abc import abstractmethod

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.orm
import sqlalchemy.sql
from builder import StatementBuilder

from quart_sqlalchemy.types import ColumnExpr
from quart_sqlalchemy.types import EntityIdT
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import ORMOption
from quart_sqlalchemy.types import Selectable


sa = sqlalchemy


class AbstractRepository(t.Generic[EntityT, EntityIdT], metaclass=ABCMeta):
    """A repository interface."""

    identity: t.Type[EntityIdT]

    # def __init__(self, model: t.Type[EntityT]):
    #     self.model = model

    @property
    def model(self) -> EntityT:
        return self.__orig_class__.__args__[0]

    @abstractmethod
    def insert(self, values: t.Dict[str, t.Any]) -> EntityT:
        """Add `values` to the collection."""

    @abstractmethod
    def update(self, id_: EntityIdT, values: t.Dict[str, t.Any]) -> EntityT:
        """Update model with model_id using values."""

    @abstractmethod
    def merge(
        self, id_: EntityIdT, values: t.Dict[str, t.Any], for_update: bool = False
    ) -> EntityT:
        """Merge model with model_id using values."""

    @abstractmethod
    def get(
        self,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> t.Optional[EntityT]:
        """Get model with model_id."""

    @abstractmethod
    def select(
        self,
        selectables: t.Sequence[Selectable] = (),
        conditions: t.Sequence[ColumnExpr] = (),
        group_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        order_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        offset: t.Optional[int] = None,
        limit: t.Optional[int] = None,
        distinct: bool = False,
        for_update: bool = False,
        include_inactive: bool = False,
        yield_by_chunk: t.Optional[int] = None,
    ) -> t.Union[sa.ScalarResult[EntityT], t.Iterator[t.Sequence[EntityT]]]:
        """Select models matching conditions."""

    @abstractmethod
    def delete(self, id_: EntityIdT) -> None:
        """Delete model with id_."""

    @abstractmethod
    def exists(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        for_update: bool = False,
        include_inactive: bool = False,
    ) -> bool:
        """Return the existence of an object matching conditions."""

    @abstractmethod
    def deactivate(self, id_: EntityIdT) -> EntityT:
        """Soft-Delete model with id_."""

    @abstractmethod
    def reactivate(self, id_: EntityIdT) -> EntityT:
        """Soft-Delete model with id_."""


class AbstractBulkRepository(t.Generic[EntityT, EntityIdT], metaclass=ABCMeta):
    """A repository interface for bulk operations.

    Note: this interface circumvents ORM internals, breaking commonly expected behavior in order
    to gain performance benefits.  Only use this class whenever absolutely necessary.
    """

    model: t.Type[EntityT]
    builder: StatementBuilder

    @abstractmethod
    def bulk_insert(
        self,
        values: t.Sequence[t.Dict[str, t.Any]] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        ...

    @abstractmethod
    def bulk_update(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        values: t.Optional[t.Dict[str, t.Any]] = None,
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        ...

    @abstractmethod
    def bulk_delete(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
    ) -> sa.Result[t.Any]:
        ...
