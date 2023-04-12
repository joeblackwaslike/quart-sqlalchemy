from __future__ import annotations

import typing as t
from datetime import datetime
from uuid import UUID
from uuid import uuid4

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
import sqlalchemy_utils
import typing_extensions as tx
from ulid import ULID


sa = sqlalchemy
sau = sqlalchemy_utils

IntPK = tx.Annotated[int, sa.orm.mapped_column(primary_key=True, autoincrement=True)]
UUID = tx.Annotated[UUID, sa.orm.mapped_column(default=uuid4)]
ULID = tx.Annotated[ULID, sa.orm.mapped_column(default=ULID)]

Created = tx.Annotated[
    datetime,
    sa.orm.mapped_column(
        default=sa.func.now(),
        server_default=sa.FetchedValue(),
    ),
]
Updated = tx.Annotated[
    datetime,
    sa.orm.mapped_column(
        default=sa.func.now(),
        onupdate=sa.func.now(),
        server_default=sa.FetchedValue(),
        server_onupdate=sa.FetchedValue(),
    ),
]

Json = tx.Annotated[
    t.Dict[t.Any, t.Any],
    sa.orm.mapped_column(sau.JSONType, default=dict),
]
