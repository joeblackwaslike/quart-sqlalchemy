"""This module is a best effort first-iteration attempt to add retry logic to sqlalchemy.

It's expected when working with a remote database to encounter exceptions related to deadlocks,
transaction isolation measures, and overall connectivity issues.  These exceptions are almost
always from the DB-API level and mostly inherit from:
    * sqlalchemy.exc.OperationalError
    * sqlalchemy.exc.InternalError

The tenacity library can be used here to add some retry logic to sqlalchemy transactions.

There are a few ways to use tenacity:
    * You can use the t`enacity.retry` decorator to decorate the callable with retry logic.
    * You can use the `tenacity.Retrying` or `tenacity.AsyncRetrying` context managers to add
      retry logic to a block of code.

WARNING:  The following code in this module is experimental and needs to be completed before anything here
can be relied on.  It probably doesn't work in it's current form.  Use the examples under Usage instead.
    * RetryingSession
    * retrying_session
    * retrying_async_session

    
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
from contextlib import asynccontextmanager
from contextlib import AsyncExitStack
from contextlib import contextmanager
from contextlib import ExitStack

import sqlalchemy
import sqlalchemy.exc
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
    stop=tenacity.stop_after_attempt(3) | tenacity.stop_after_delay(5),
    wait=tenacity.wait_exponential(max=6, exp_base=1.5),
    before_sleep=tenacity.before_sleep_log(logger, logging.INFO),
)

retryable = tenacity.retry(**retry_config)
retry_context = tenacity.Retrying(**retry_config)


class RetryingSession(sa.orm.Session):
    @tenacity.retry(**retry_config)
    def _execute_internal(self, *args, **kwargs):
        return super()._execute_internal(*args, **kwargs)


@contextmanager
def retrying_session(bind, begin=True, **kwargs):
    try:
        for attempt in tenacity.Retrying(**retry_config, **kwargs):
            with attempt:
                print("attempt", attempt.retry_state.attempt_number)
                with bind.Session() as session:
                    with ExitStack() as stack:
                        if begin:
                            stack.enter_context(session.begin())
                        yield session
    except tenacity.RetryError:
        pass


@asynccontextmanager
async def retrying_async_session(bind, begin=True, **kwargs):
    try:
        async for attempt in tenacity.AsyncRetrying(**retry_config, **kwargs):
            with attempt:
                async with bind.Session() as session:
                    async with AsyncExitStack() as stack:
                        if begin:
                            await stack.enter_async_context(session.begin())
                        yield session
    except tenacity.RetryError:
        pass
