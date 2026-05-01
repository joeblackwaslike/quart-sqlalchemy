import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm

from quart_sqlalchemy import SQLAlchemy

from .. import base

sa = sqlalchemy


class TestAsyncBind(base.AsyncTestBase):
    async def test_async_transactional_orm_flow(self, db: SQLAlchemy, Todo: type[t.Any]):
        """Test basic async ORM operations with transactions."""
        async with db.bind.Session() as s:
            async with s.begin():
                todo = Todo(title="hello")
                s.add(todo)
                await s.flush()
                await s.refresh(todo)

        async with db.bind.Session() as s:
            async with s.begin():
                select_todo = (await s.scalars(sa.select(Todo).where(Todo.id == todo.id))).one()
                assert todo == select_todo

    async def test_async_session_rollback(self, db: SQLAlchemy, Todo: type[t.Any]):
        """Test that async session explicit rollback prevents data persistence."""
        todo_id = None
        async with db.bind.Session() as s:
            async with s.begin():
                todo = Todo(title="should_rollback")
                s.add(todo)
                await s.flush()
                await s.refresh(todo)
                todo_id = todo.id
                await s.rollback()  # Explicit rollback

        # Verify todo was not persisted
        async with db.bind.Session() as s:
            result = await s.scalars(sa.select(Todo).where(Todo.id == todo_id))
            assert result.first() is None

    async def test_async_session_explicit_commit(self, db: SQLAlchemy, Todo: type[t.Any]):
        """Test explicit commit in async session."""
        todo_id = None
        async with db.bind.Session() as s:
            async with s.begin():
                todo = Todo(title="explicit_commit")
                s.add(todo)
                await s.flush()
                await s.refresh(todo)
                todo_id = todo.id
                await s.commit()

        # Verify todo was persisted
        async with db.bind.Session() as s:
            result = await s.scalars(sa.select(Todo).where(Todo.id == todo_id))
            found_todo = result.first()
            assert found_todo is not None
            assert found_todo.title == "explicit_commit"

    async def test_async_session_exception_rollback(self, db: SQLAlchemy, Todo: type[t.Any]):
        """Test that exceptions trigger automatic rollback."""
        todo_id = None
        try:
            async with db.bind.Session() as s:
                async with s.begin():
                    todo = Todo(title="will_fail")
                    s.add(todo)
                    await s.flush()
                    await s.refresh(todo)
                    todo_id = todo.id
                    raise ValueError("Intentional test error")
        except ValueError:
            pass

        # Verify todo was rolled back
        async with db.bind.Session() as s:
            result = await s.scalars(sa.select(Todo).where(Todo.id == todo_id))
            assert result.first() is None

    async def test_async_multiple_sessions_isolation(
        self, db: SQLAlchemy, Todo: type[t.Any]
    ):
        """Test that multiple async sessions maintain isolation."""
        # Create todo in first session
        async with db.bind.Session() as s1:
            async with s1.begin():
                todo = Todo(title="session1")
                s1.add(todo)
                await s1.flush()
                await s1.refresh(todo)
                todo_id = todo.id

        # Verify in second session
        async with db.bind.Session() as s2:
            result = await s2.scalars(sa.select(Todo).where(Todo.id == todo_id))
            found_todo = result.first()
            assert found_todo is not None
            assert found_todo.title == "session1"

    async def test_async_bind_session_factory_creation(self, db: SQLAlchemy):
        """Test that async session factory is properly configured."""
        assert db.bind.Session is not None
        assert isinstance(db.bind.Session, sa.ext.asyncio.async_sessionmaker)

    async def test_async_bind_engine_creation(self, db: SQLAlchemy):
        """Test that async engine is properly configured."""
        assert db.bind.engine is not None
        assert isinstance(db.bind.engine, sa.ext.asyncio.AsyncEngine)

    async def test_async_bind_url_property(self, db: SQLAlchemy):
        """Test that bind URL property returns correct value."""
        url = db.bind.url
        assert url is not None
        assert isinstance(url, str)
        assert "aiosqlite" in url

    async def test_async_bind_repr(self, db: SQLAlchemy):
        """Test AsyncBind string representation."""
        repr_str = repr(db.bind)
        assert "AsyncBind" in repr_str
        assert "sqlite" in repr_str.lower()

    async def test_async_relationship_loading(
        self, db: SQLAlchemy, User: type[t.Any], Todo: type[t.Any]
    ):
        """Test async loading of relationships."""
        async with db.bind.Session() as s:
            async with s.begin():
                user = User(name="test_user")
                todo1 = Todo(title="todo1", user=user)
                todo2 = Todo(title="todo2", user=user)
                s.add(user)
                await s.flush()
                await s.refresh(user)
                user_id = user.id

        async with db.bind.Session() as s:
            result = await s.scalars(
                sa.select(User)
                .where(User.id == user_id)
                .options(sa.orm.selectinload(User.todos))
            )
            loaded_user = result.one()
            assert len(loaded_user.todos) == 2
            assert {t.title for t in loaded_user.todos} == {"todo1", "todo2"}

    async def test_async_test_transaction_rollback(
        self, db: SQLAlchemy, Todo: type[t.Any]
    ):
        """Test that async test transactions properly rollback."""
        todo_id = None
        async with db.bind.test_transaction(savepoint=True) as tx:
            async with tx.Session() as s:
                async with s.begin():
                    todo = Todo(title="test_transaction")
                    s.add(todo)
                    await s.flush()
                    await s.refresh(todo)
                    todo_id = todo.id

            # Verify todo exists within transaction
            async with tx.Session() as s:
                result = await s.scalars(sa.select(Todo).where(Todo.id == todo_id))
                assert result.one() is not None

        # Verify todo was rolled back after transaction
        async with db.bind.Session() as s:
            result = await s.scalars(sa.select(Todo).where(Todo.id == todo_id))
            assert result.first() is None


class TestBindContext(base.ComplexTestBase):
    def test_bind_context_execution_isolation_level(self, db: SQLAlchemy, Todo: type[t.Any]):
        with db.bind.context(engine_execution_options=dict(isolation_level="SERIALIZABLE")) as ctx:
            engine_execution_options = ctx.engine.get_execution_options()
            assert engine_execution_options["isolation_level"] == "SERIALIZABLE"

            with ctx.Session() as s:
                with s.begin():
                    todo = Todo(title="hello")
                    s.add(todo)
                    s.flush()
                    s.refresh(todo)


class TestTestTransaction(base.ComplexTestBase):
    def test_test_transaction_for_orm(self, db: SQLAlchemy, Todo: type[t.Any]):
        with db.bind.test_transaction(savepoint=True) as tx:
            with tx.Session() as s:
                todo = Todo(title="hello")
                s.add(todo)
                s.commit()
                s.refresh(todo)

            with tx.Session() as s:
                select_todo = s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()

            assert select_todo == todo

        with db.bind.Session() as s:
            with pytest.raises(sa.orm.exc.NoResultFound):
                s.scalars(sa.select(Todo).where(Todo.id == todo.id)).one()
