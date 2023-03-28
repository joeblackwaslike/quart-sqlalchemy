from __future__ import annotations

import typing as t

import sqlalchemy
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.sql
import typing_extensions as tx
from sqlalchemy.orm.interfaces import ORMOption as _ORMOption
from sqlalchemy.sql._typing import _ColumnExpressionArgument
from sqlalchemy.sql._typing import _ColumnsClauseArgument
from sqlalchemy.sql._typing import _DMLTableArgument


sa = sqlalchemy

SessionT = t.TypeVar("SessionT", bound=sa.orm.Session)
EntityT = t.TypeVar("EntityT", bound=sa.orm.DeclarativeBase)
EntityIdT = t.TypeVar("EntityIdT", bound=t.Any)

ColumnExpr = _ColumnExpressionArgument
Selectable = _ColumnsClauseArgument
DMLTable = _DMLTableArgument
ORMOption = _ORMOption

TransactionIsolationLevel = tx.Literal[
    "AUTOCOMMIT",
    "READ COMMITTED",
    "READ UNCOMMITTED",
    "REPEATABLE READ",
    "SERIALIZABLE",
]
BoundParamStyle = tx.Literal["qmark", "numeric", "named", "format"]
SessionBindKey = t.Union[t.Type[t.Any], sa.orm.Mapper[t.Any], sa.sql.TableClause, str]
SessionBind = t.Union[sa.Engine, sa.Connection]
SynchronizeSession = tx.Literal[False, "auto", "evaluate", "fetch"]
DMLStrategy = tx.Literal["bulk", "raw", "orm", "auto"]

SABind = t.Union[
    sa.Engine, sa.Connection, sa.ext.asyncio.AsyncEngine, sa.ext.asyncio.AsyncConnection
]
