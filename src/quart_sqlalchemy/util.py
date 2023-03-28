from __future__ import annotations

import functools
import re
import typing as t

import sqlalchemy
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import sqlalchemy.util


sa = sqlalchemy


T = t.TypeVar("T")


class lazy_property(t.Generic[T]):
    """Lazily-evaluated property decorator.

    This class is an implementation of a non-overriding descriptor.  Translation: it implements
    the __get__ method but not the __set__ method.  That allows it to be shadowed by directly
    setting a value in the instance dictionary of the same name.  That means the first time this
    descriptor is accessed, the value is computed using the provided factory.  That value is then
    set directly in the instance dictionary, meaning all further reads will be shadowed by the
    value that was set in the instance dictionary.  Think of this like the perfect lazy-loaded
    attribute.

    Since `factory` is a callable, this class can be used as a decorator, much like the builtin
    `property`.  The decorated method will be replaced with this descriptor, and used to lazily
    compute and cache the value on first access.

    Usage:
        >>> class MyClass:
        ...     @lazy_property
        ...     def expensive_computation(self):
        ...         print('Computing value')
        ...         time.sleep(3)
        ...         return 'large prime number'
        ...
        ... my_class = MyClass()
        >>> my_class.expensive_computation
        Computing value
        'large prime number'
        >>> my_class.expensive_computation
        'large prime number'

    Ref: https://docs.python.org/3/howto/descriptor.html#definition-and-introduction
    """

    def __init__(self, factory: t.Callable[[t.Any], T]):
        self.factory = factory
        self.name = factory.__name__
        # update self (descriptor) to look like the factory function
        functools.update_wrapper(self, factory)

    def __get__(self, instance: t.Any, type_: t.Optional[t.Any] = None) -> T:
        if instance is None:
            return self

        instance.__dict__[self.name] = self.factory(instance)
        return instance.__dict__[self.name]


def sqlachanges(sa_object):
    """
    Returns the changes made to this object so far this session, in {'propertyname': [listofvalues] } format.
    """
    attrs = sa.inspect(sa_object).attrs
    return {a.key: list(reversed(a.history.sum())) for a in attrs if len(a.history.sum()) > 1}


def camel_to_snake_case(name: str) -> str:
    """Convert a ``CamelCase`` name to ``snake_case``."""
    name = re.sub(r"((?<=[a-z0-9])[A-Z]|(?!^)[A-Z](?=[a-z]))", r"_\1", name)
    return name.lower().lstrip("_")
