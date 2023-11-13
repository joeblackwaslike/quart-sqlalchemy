from __future__ import annotations

import typing as t

import sqlalchemy.event
import sqlalchemy.orm


sa = sqlalchemy

SessionT = t.TypeVar("SessionT", bound=sa.orm.Session)
EntityT = t.TypeVar("EntityT", bound=sa.orm.DeclarativeBase)
EntityIdT = t.TypeVar("EntityIdT", bound=int)


class SQLAlchemyRepository(t.Generic[SessionT, EntityT]):
    """A repository that uses SQLAlchemy to persist data."""

    session: SessionT
    model: EntityT

    def __init__(self, session: SessionT):
        self.session = session

    def get(self, entity_id: EntityIdT) -> EntityT:
        self.session.get(entity_id)

    def get_by(
        self,
        clauses: t.Iterable[t.Any] = (),
        options: t.Iterable[t.Any] = (),
    ) -> list[EntityT]:
        statement = sa.select(self.model).where(*clauses).options(*options)
        return self.session.scalars(statement).all()

    def add(self, entity: EntityT) -> EntityT:
        self.session.add(entity)
        self.session.flush()
        return entity

    def update(self, entity: EntityT, **update_kwargs) -> EntityT:
        for key, value in update_kwargs.items():
            setattr(entity, key, value)
        self.session.add(entity)
        self.session.flush()
        self.session.refresh(entity)
        return entity

    def delete(self, entity: EntityT) -> None:
        self.session.delete(entity)
        self.session.flush()
