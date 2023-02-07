import sqlalchemy


sa = sqlalchemy

simple_config = {
    "SQLALCHEMY_DATABASE_URI": "sqlite://",
    "SQLALCHEMY_ECHO": False,
    "SQLALCHEMY_ENGINE_OPTIONS": dict(
        connect_args=dict(
            check_same_thread=True,
        ),
    ),
}
async_config = {
    "SQLALCHEMY_DATABASE_URI": "sqlite+aiosqlite://",
    "SQLALCHEMY_ENGINE_OPTIONS": dict(
        connect_args=dict(
            check_same_thread=True,
        ),
    ),
}
complex_config = {
    "SQLALCHEMY_BINDS": {
        None: dict(
            url="sqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "read-replica": dict(
            url="sqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "async": dict(
            url="sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
    },
    "SQLALCHEMY_ECHO": False,
}
