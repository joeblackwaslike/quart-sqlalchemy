from __future__ import annotations

from typing import Any

from quart import Quart

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.cli import add_models_to_shell


async def test_shell_context(app: Quart, db: SQLAlchemy, Todo: Any) -> None:
    async with app.app_context():
        context = add_models_to_shell()
        assert context["db"] is db
        assert context["Todo"] is Todo
