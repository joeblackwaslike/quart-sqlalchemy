from __future__ import annotations

import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util
import sqlalchemy_utils
import typing_extensions as tx


sa = sqlalchemy
sau = sqlalchemy_utils


PrimaryKey = tx.Annotated[int, sa.orm.mapped_column(sa.Identity(), primary_key=True)]
CreatedTimestamp = tx.Annotated[
    datetime,
    sa.orm.mapped_column(
        default=sa.func.now(),
        server_default=sa.FetchedValue(),
    ),
]
UpdatedTimestamp = tx.Annotated[
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
    sa.orm.mapped_column(sau.JSONType, default_factory=dict),
]
