from contextlib import contextmanager

from quart import g
from quart import Quart
from quart import signals

from quart_sqlalchemy import Bind


@contextmanager
def global_bind(app: Quart, bind: Bind):
    def handler(sender, **kwargs):
        g.bind = bind

    with signals.appcontext_pushed.connected_to(handler, app):
        yield
