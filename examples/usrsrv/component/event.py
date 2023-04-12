from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from functools import singledispatch
from uuid import UUID
from uuid import uuid1

from .command import Command
from .command import CommandID
from .entity import Entity
from .entity import EntityID


EventID = UUID


class Event:
    command_id: CommandID
    event_id: EventID = field(default_factory=uuid1)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Created(Event):
    command_id: CommandID
    uow_id: EntityID
    event_id: EventID = field(default_factory=uuid1)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Updated(Event):
    command_id: CommandID
    event_id: EventID = field(default_factory=uuid1)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@singledispatch
def app_event(event: Entity.Event, command: Command) -> Event:
    raise NotImplementedError


@app_event.register(Entity.Updated)
def _(event: Entity.Updated, command: Command) -> Updated:
    return Updated(command.command_id)
