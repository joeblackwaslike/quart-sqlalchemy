import asyncio
import contextvars
import functools
import traceback
from pathlib import Path

import pytest
from quart import current_app
from quart import Quart
from quart.ctx import has_app_context


blah = contextvars.ContextVar("blah")


@pytest.fixture
async def my_context_var():
    blah.set("hello")
    assert blah.get() == "hello"
    yield blah


async def test_context_propagates_from_fixture(my_context_var):
    """
    For this to pass, the commandline flag `--py311-task` or pytest.ini config must contain:
    ```
    py311_task = true
    ```
    This serves as proof that the experimental patch for pytest-asyncio finally allows for proper
    context propagation.
    """
    assert blah.get() == "hello"


@pytest.fixture
async def dummy_fixture():
    before = id(asyncio.current_task())
    yield
    after = id(asyncio.current_task())

    assert before == after


async def test_async_fixture_setup_and_finalize_run_in_same_asyncio_task(dummy_fixture):
    # This passes if no exceptions thrown in dummy_fixture
    assert True


@pytest.fixture
def app():
    return Quart(__name__)


@pytest.fixture
async def app_ctx(app):
    before = id(asyncio.current_task())
    print("before:", before)
    async with app.app_context():
        yield
    after = id(asyncio.current_task())
    print("after:", after)

    assert before == after


async def test_has_app_context(app, app_ctx):
    print("in-test:", id(asyncio.current_task()))
    assert has_app_context()


async def test_current_app(app, app_ctx):
    print("in-test:", id(asyncio.current_task()))
    assert current_app._get_current_object()
