from contextlib import contextmanager

from quart import g
from quart import signals


@contextmanager
def user_set(app, user):
    def handler(sender, **kwargs):
        g.user = user

    with signals.appcontext_pushed.connected_to(handler, app):
        yield
