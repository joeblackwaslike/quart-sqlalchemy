from quart_sqlalchemy import Base


simple_mapping_config = {
    "model_class": Base,
    "binds": {
        "default": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        }
    },
}

complex_mapping_config = {
    "model_class": Base,
    "binds": {
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
}

async_mapping_config = {
    "model_class": Base,
    "binds": {
        "default": {
            "engine": {"url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        }
    },
}
