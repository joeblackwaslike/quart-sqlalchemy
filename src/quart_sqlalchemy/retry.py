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


# https://tenacity.readthedocs.io/en/latest/
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
