"""Retry logic for SQLAlchemy database operations.

When working with remote databases, it's expected to encounter exceptions related to
deadlocks, transaction isolation, and connectivity issues. These exceptions typically
inherit from:
    * sqlalchemy.exc.OperationalError
    * sqlalchemy.exc.InternalError

This module provides retry configuration using the tenacity library.

Usage:

Example decorator usage:

    ```python
    @tenacity.retry(**config)
    def add_user_post(db, user_id, post_values):
        with db.bind.Session() as session:
            with session.begin():
                user = session.scalars(sa.select(User).where(User.id == user_id)).one()
                post = Post(user=user, **post_values)
                session.add(post)
                session.flush()
                session.refresh(post)
        return post
    ```

Example async decorator usage:

    ```python
    @tenacity.retry(**config)
    async def add_user_post(db, user_id, post_values):
        async_bind = db.get_bind("async")
        async with async_bind.Session() as session:
            async with session.begin():
                user = (await session.scalars(sa.select(User).where(User.id == user_id))).one()
                post = Post(user=user, **post_values)
                session.add(post)
                await session.commit()
                await session.refresh(post)
        return post
    ```

Example context manager usage:

    ```python
    try:
        for attempt in tenacity.Retrying(**config):
            with attempt:
                with db.bind.Session() as session:
                    with session.begin():
                        obj = session.scalars(sa.select(User).where(User.id == 1)).one()
                        post = Post(title="new post", user=obj)
                        session.add(Post)
    except tenacity.RetryError:
        pass
    ```

Example async context manager usage:

    ```python
    async_bind = db.get_bind("async")
    try:
        async for attempt in tenacity.AsyncRetrying(**config):
            with attempt:
                async with async_bind.Session() as session:
                    async with session.begin():
                        obj = (await session.scalars(sa.select(User).where(User.id == 1))).one()
                        post = Post(title="new post", user=obj)
                        session.add(Post)
                        await session.commit()
    except tenacity.RetryError:
        pass
    ```

Check out the docs: https://tenacity.readthedocs.io/en/latest/
Check out the repo: https://github.com/jd/tenacity
"""

import logging
import typing as t
from contextlib import asynccontextmanager, contextmanager

import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.ext.asyncio
import sqlalchemy.orm
import tenacity

sa = sqlalchemy

logger = logging.getLogger(__name__)


_RETRY_ERRORS = (
    sa.exc.InternalError,
    sa.exc.InvalidRequestError,
    sa.exc.OperationalError,
)


retry_config = dict(
    reraise=True,
    retry=tenacity.retry_if_exception_type(_RETRY_ERRORS)
    | tenacity.retry_if_exception_message(match="Too many connections"),
    stop=tenacity.stop_after_attempt(3) | tenacity.stop_after_delay(10),
    wait=tenacity.wait_exponential(max=10, exp_base=1.5),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
)


@contextmanager
def retrying_session(bind: t.Any, **kwargs: t.Any) -> t.Generator[sa.orm.Session, None, None]:
    """Context manager providing a database session with automatic retry logic.

    WARNING: This function is experimental and may not handle all edge cases.
    For production use, prefer using tenacity.retry() decorator directly on your
    business logic functions.

    Args:
        bind: Database bind object with a Session factory
        **kwargs: Additional retry configuration to override retry_config defaults

    Yields:
        Session: SQLAlchemy session with automatic transaction management

    Raises:
        tenacity.RetryError: When all retry attempts are exhausted (re-raised after logging)

    Example:
        >>> with retrying_session(db.bind) as session:
        ...     user = session.scalars(sa.select(User).where(User.id == 1)).one()
        ...     user.name = "Updated"
        ...     session.commit()
    """
    try:
        for attempt in tenacity.Retrying(**retry_config, **kwargs):  # type: ignore[arg-type]
            with attempt:
                logger.info("Retry attempt %d", attempt.retry_state.attempt_number)
                with bind.Session() as session:
                    yield session
    except tenacity.RetryError:
        logger.exception("All retry attempts exhausted for database operation")
        raise


@asynccontextmanager
async def retrying_async_session(
    bind: t.Any, **kwargs: t.Any
) -> t.AsyncGenerator[sa.ext.asyncio.AsyncSession, None]:
    """Async context manager providing a database session with automatic retry logic.

    WARNING: This function is experimental and may not handle all edge cases.
    For production use, prefer using tenacity.retry() decorator directly on your
    async business logic functions.

    Args:
        bind: Async database bind object with an AsyncSession factory
        **kwargs: Additional retry configuration to override retry_config defaults

    Yields:
        AsyncSession: SQLAlchemy async session with automatic transaction management

    Raises:
        tenacity.RetryError: When all retry attempts are exhausted (re-raised after logging)

    Example:
        >>> async with retrying_async_session(db.async_bind) as session:
        ...     user = (await session.scalars(sa.select(User).where(User.id == 1))).one()
        ...     user.name = "Updated"
        ...     await session.commit()
    """
    try:
        async for attempt in tenacity.AsyncRetrying(**retry_config, **kwargs):  # type: ignore[arg-type]
            with attempt:
                async with bind.Session() as session:
                    yield session
    except tenacity.RetryError:
        logger.exception("All retry attempts exhausted for async database operation")
        raise
