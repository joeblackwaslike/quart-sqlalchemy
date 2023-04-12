import inspect
import typing as t
from contextlib import contextmanager
from functools import wraps


RT = t.TypeVar("RT")


@contextmanager
def create_session(bind):
    """Contextmanager that will create and teardown a session."""
    session = bind.Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def provide_session(bind_name: str = "default"):
    """
    Function decorator that provides a session if it isn't provided.
    If you want to reuse a session or run the function as part of a
    database transaction, you pass it to the function, if not this wrapper
    will create one and close it for you.
    """

    def decorator(func: t.Callable[..., RT]) -> t.Callable[..., RT]:
        from quart_sqlalchemy import Bind

        func_params = inspect.signature(func).parameters
        try:
            # func_params is an ordered dict -- this is the "recommended" way of getting the position
            session_args_idx = tuple(func_params).index("session")
        except ValueError:
            raise ValueError(f"Function {func.__qualname__} has no `session` argument") from None

        # We don't need this anymore -- ensure we don't keep a reference to it by mistake
        del func_params

        @wraps(func)
        def wrapper(*args, **kwargs) -> RT:
            if "session" in kwargs or session_args_idx < len(args):
                return func(*args, **kwargs)
            bind = Bind.get_instance(bind_name)

            with create_session(bind) as session:
                return func(*args, session=session, **kwargs)

        return wrapper

    return decorator
