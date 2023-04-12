from typing import NewType
from typing import Optional
from typing import Text
from uuid import UUID
from uuid import uuid1


EntityID = NewType("EntityID", UUID)


class EntityDTO:
    id: EntityID
    value: Optional[Text]


class Entity:
    id: EntityID
    dto: EntityDTO

    class Event:
        pass

    class Updated(Event):
        pass

    def __init__(self, dto: EntityDTO) -> None:
        self.id = dto.id
        self.dto = dto

    @classmethod
    def create(cls) -> "Entity":
        dto = EntityDTO()
        dto.id = EntityID(uuid1())
        dto.value = None
        return Entity(dto)

    def update(self, value: Text) -> Updated:
        self.dto.value = value
        return self.Updated()
