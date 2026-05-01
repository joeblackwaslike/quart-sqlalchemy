import re
import typing as t

import sqlalchemy

sa = sqlalchemy


def sqlachanges(sa_object: t.Any) -> dict[str, list[t.Any]]:
    """Returns the changes made to this object so far this session, in {'propertyname': [listofvalues] } format."""
    attrs = sa.inspect(sa_object).attrs
    return {a.key: list(reversed(a.history.sum())) for a in attrs if len(a.history.sum()) > 1}


def camel_to_snake_case(name: str) -> str:
    """Convert a ``CamelCase`` name to ``snake_case``."""
    name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", name)
    return name.lower().lstrip("_")
