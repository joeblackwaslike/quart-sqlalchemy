import typing as t
from abc import ABCMeta, abstractmethod

import sqlalchemy
from builder import StatementBuilder

from quart_sqlalchemy.types import ColumnExpr, EntityIdT, EntityT, ORMOption, Selectable

sa = sqlalchemy


class AbstractRepository(t.Generic[EntityT, EntityIdT], metaclass=ABCMeta):
    """A repository interface."""

    identity: type[EntityIdT]

    # def __init__(self, model: t.Type[EntityT]):
    #     self.model = model

    @property
    def model(self) -> EntityT:
        return self.__orig_class__.__args__[0]

    @abstractmethod
    def insert(self, values: dict[str, t.Any]) -> EntityT:
        """Add `values` to the collection."""

    @abstractmethod
    def update(self, id_: EntityIdT, values: dict[str, t.Any]) -> EntityT:
        """Update model with model_id using values."""

    @abstractmethod
    def merge(self, id_: EntityIdT, values: dict[str, t.Any], for_update: bool = False) -> EntityT:
        """Merge model with model_id using values."""

    @abstractmethod
    def get(
        self,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: dict[str, t.Any] | None = None,
        for_update: bool = False,
        include_soft_deleted: bool = False,
    ) -> EntityT | None:
        """Get model with model_id."""

    @abstractmethod
    def select(
        self,
        selectables: t.Sequence[Selectable] = (),
        conditions: t.Sequence[ColumnExpr] = (),
        group_by: t.Sequence[ColumnExpr | str] = (),
        order_by: t.Sequence[ColumnExpr | str] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: dict[str, t.Any] | None = None,
        offset: int | None = None,
        limit: int | None = None,
        distinct: bool = False,
        for_update: bool = False,
        include_soft_deleted: bool = False,
        yield_by_chunk: int | None = None,
    ) -> sa.ScalarResult[EntityT] | t.Iterator[t.Sequence[EntityT]]:
        """Select models matching conditions."""

    @abstractmethod
    def delete(self, id_: EntityIdT) -> None:
        """Delete model with id_."""

    @abstractmethod
    def exists(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        for_update: bool = False,
        include_soft_deleted: bool = False,
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

    model: type[EntityT]
    builder: StatementBuilder

    @abstractmethod
    def bulk_insert(
        self,
        values: t.Sequence[dict[str, t.Any]] = (),
        execution_options: dict[str, t.Any] | None = None,
    ) -> sa.Result[t.Any]: ...

    @abstractmethod
    def bulk_update(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        values: dict[str, t.Any] | None = None,
        execution_options: dict[str, t.Any] | None = None,
    ) -> sa.Result[t.Any]: ...

    @abstractmethod
    def bulk_delete(
        self,
        conditions: t.Sequence[ColumnExpr] = (),
        execution_options: dict[str, t.Any] | None = None,
    ) -> sa.Result[t.Any]: ...
