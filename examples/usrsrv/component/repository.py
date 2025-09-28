from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy.orm import registry
from sqlalchemy.orm import Session

from . import EntityID
from .entity import Entity
from .entity import EntityDTO
from .exception import NotFound
from .service import Repository


metadata = MetaData()
mapper_registry = registry(metadata=metadata)


entities_table = Table(
    "entities",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("uuid", String, unique=True, index=True),
    Column("value", String, nullable=True),
)

# EntityMapper = mapper(
#     EntityDTO,
#     entities_table,
#     properties={
#         "id": entities_table.c.uuid,
#         "value": entities_table.c.value,
#     },
#     column_prefix="_db_column_",
# )

EntityMapper = mapper_registry.map_imperatively(
    EntityDTO,
    entities_table,
    properties={
        "id": entities_table.c.uuid,
        "value": entities_table.c.value,
    },
    column_prefix="_db_column_",
)


class ORMRepository(Repository):
    def __init__(self, session: Session):
        self._session = session
        self._query = select(EntityMapper)

    def get(self, entity_id: EntityID) -> Entity:
        if dto := self._session.scalars(
            self._query.filter_by(uuid=entity_id)
        ).one_or_none():
            return Entity(dto)
        else:
            raise NotFound(entity_id)

    def save(self, entity: Entity) -> None:
        self._session.add(entity.dto)
        self._session.flush()
