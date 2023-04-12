from abc import ABC
from abc import abstractmethod
from functools import singledispatch
from typing import Callable
from typing import List
from typing import Optional

from .command import Command
from .command import Create
from .command import UpdateValue
from .entity import Entity
from .entity import EntityID
from .event import app_event
from .event import Created
from .event import Event


Listener = Callable[[Event], None]


class Repository(ABC):
    @abstractmethod
    def get(self, entity_id: EntityID) -> Entity:
        raise NotImplementedError

    @abstractmethod
    def save(self, entity: Entity) -> None:
        raise NotImplementedError


class CommandHandler:
    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._listeners: List[Listener] = []
        super().__init__()

    def register(self, listener: Listener) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unregister(self, listener: Listener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    @singledispatch
    def handle(self, command: Command) -> Optional[Event]:
        entity: Entity = self._repository.get(command.entity_id)

        event: Event = app_event(self._handle(command, entity), command)
        for listener in self._listeners:
            listener(event)

        self._repository.save(entity)
        return event

    @handle.register(Create)
    def create(self, command: Create) -> Event:
        entity = Entity.create()
        self._repository.save(entity)
        return Created(command.command_id, entity.id)

    @singledispatch
    def _handle(self, c: Command, u: Entity) -> Entity.Event:
        raise NotImplementedError

    @_handle.register(UpdateValue)
    def _(self, command: UpdateValue, entity: Entity) -> Entity.Event:
        return entity.update(command.value)
