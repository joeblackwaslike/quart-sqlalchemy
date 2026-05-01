import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.sql
from sqlalchemy.orm.interfaces import ORMOption as _ORMOption
from sqlalchemy.sql._typing import (
    _ColumnExpressionArgument,
    _ColumnsClauseArgument,
    _DMLTableArgument,
)

sa = sqlalchemy

SessionT = t.TypeVar("SessionT", bound=sa.orm.Session)
EntityT = t.TypeVar("EntityT", bound=sa.orm.DeclarativeBase)
EntityIdT = t.TypeVar("EntityIdT", bound=t.Any)

ColumnExpr = _ColumnExpressionArgument[t.Any]
Selectable = _ColumnsClauseArgument[t.Any]
DMLTable = _DMLTableArgument
ORMOption = _ORMOption

TransactionIsolationLevel = t.Literal[
    "AUTOCOMMIT",
    "READ COMMITTED",
    "READ UNCOMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
]
BoundParamStyle = t.Literal["qmark", "numeric", "named", "format"]
SessionBindKey = type[t.Any] | sa.orm.Mapper[t.Any] | sa.sql.TableClause | str
SessionBind = sa.Engine | sa.Connection
SynchronizeSession = t.Literal[False, "auto", "evaluate", "fetch"]
DMLStrategy = t.Literal["bulk", "raw", "orm", "auto"]

SABind = sa.Engine | sa.Connection | sa.ext.asyncio.AsyncEngine | sa.ext.asyncio.AsyncConnection
