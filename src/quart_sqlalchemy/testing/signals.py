from __future__ import annotations

import sqlalchemy
import sqlalchemy.orm
from blinker import Namespace
from quart.signals import AsyncNamespace


sa = sqlalchemy

sync_signals = Namespace()
async_signals = AsyncNamespace()


load_test_fixtures = sync_signals.signal(
    "quart-sqlalchemy.testing.fixtures.load.sync",
    doc="""Fired to load test fixtures into a freshly instantiated test database.

    No default signal handlers exist for this signal as the logic is very application dependent.

    Example:

        @signals.framework_extension_load_fixtures.connect
        def handle(sender: QuartSQLAlchemy, app: Quart):
            bind = sender.get_bind("default")
            with bind.Session() as session:
                with session.begin():
                    session.add_all(
                        [
                            models.User(username="user1"),
                            models.User(username="user2"),
                        ]
                    )
                    session.commit()

    Handler signature:
        def handle(sender: QuartSQLAlchemy, app: Quart):
            ...
    """,
)
