from quart_sqlalchemy import Base


simple_config = {
    "SQLALCHEMY_BINDS": {
        "default": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        }
    },
    "SQLALCHEMY_BASE_CLASS": Base,
}

complex_config = {
    "SQLALCHEMY_BINDS": {
        "default": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        },
        "read-replica": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
            "read_only": True,
        },
        "async": {
            "engine": {"url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        },
    },
    "SQLALCHEMY_BASE_CLASS": Base,
}

async_config = {
    "SQLALCHEMY_BINDS": {
        "default": {
            "engine": {"url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        },
    },
    "SQLALCHEMY_BASE_CLASS": Base,
}
