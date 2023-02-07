from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
from sqlalchemy.engine.result import _RowData
from sqlalchemy.orm._typing import _O as DataObjType
from sqlalchemy.orm.session import _EntityBindKey as DataObjEntity


sa = sqlalchemy

AnyCallableType = t.Callable[..., t.Any]

EngineType = t.Union[sa.Engine, sa.ext.asyncio.AsyncEngine]
EngineClassType = t.Type[EngineType]
SessionType = t.Union[
    sa.orm.sessionmaker[sa.orm.Session],
    sa.ext.asyncio.async_sessionmaker[sa.ext.asyncio.AsyncSession],
]
SessionFactoryType = t.Type[SessionType]

ScopedSessionType = t.Union[sa.orm.scoped_session, sa.ext.asyncio.async_scoped_session]
ScopedSessionFactoryType = t.Type[ScopedSessionType]

EntityType = DataObjEntity[DataObjType]
IdentType = t.Union[t.Any, t.Tuple[t.Any, ...]]
RowDataType = _RowData
