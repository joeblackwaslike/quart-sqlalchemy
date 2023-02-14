import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy


sa = sqlalchemy


class TestContextCaching:
    @pytest.fixture
    def app(self):
        app = Quart(__name__)
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
        return app

    @pytest.fixture
    async def db(self, app: Quart):
        return SQLAlchemy(app, context_caching_enabled=True)

    @pytest.fixture
    async def Todo(self, db: SQLAlchemy, app: Quart):
        class Todo(db.Model):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)

        async with app.app_context():
            db.create_all()

        yield Todo

        async with app.app_context():
            db.drop_all()

    async def test_caching_enabled_no_context_required_engine(self, app: Quart, db: SQLAlchemy):
        assert db.engine is db.engine

    async def test_caching_enabled_no_context_required_session_context(
        self, app: Quart, db: SQLAlchemy, Todo
    ):
        with db.session() as session:
            todo = Todo()
            session.add(todo)

            session.commit()
            session.refresh(todo)
            result = session.get(Todo, todo.id)
            assert result is todo

    async def test_caching_enabled_no_context_required_scoped_session(
        self, app: Quart, db: SQLAlchemy, Todo
    ):
        todo = Todo()
        db.session.add(todo)

        db.session.commit()
        db.session.refresh(todo)
        result = db.session.get(Todo, todo.id)
        assert result is todo
