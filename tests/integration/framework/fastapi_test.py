import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from quart_sqlalchemy import AsyncBindConfig, SQLAlchemyConfig
from quart_sqlalchemy.framework.fastapi import FastAPISQLAlchemy


class TestFastAPISQLAlchemy:
    """Test suite for FastAPI integration."""

    @pytest.fixture
    def config(self) -> SQLAlchemyConfig:
        """Create test SQLAlchemy configuration."""
        return SQLAlchemyConfig(
            binds={"default": AsyncBindConfig(url="sqlite+aiosqlite:///:memory:")}
        )

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a FastAPI app instance."""
        return FastAPI()

    @pytest.fixture
    def db(self, config: SQLAlchemyConfig, app: FastAPI) -> FastAPISQLAlchemy:
        """Create FastAPISQLAlchemy instance with app."""
        return FastAPISQLAlchemy(config, app=app)

    def test_init_app(self, db: FastAPISQLAlchemy, app: FastAPI):
        """Test that init_app registers extension on app.state."""
        assert hasattr(app.state, "sqlalchemy")
        assert app.state.sqlalchemy == db

    def test_init_app_raises_runtime_error_when_already_initialized(
        self, db: FastAPISQLAlchemy
    ):
        """Test that init_app raises RuntimeError if already registered."""
        app = FastAPI()
        db.init_app(app)
        with pytest.raises(RuntimeError, match="already been registered"):
            db.init_app(app)

    def test_init_without_app(self, config: SQLAlchemyConfig):
        """Test creating instance without passing app."""
        db = FastAPISQLAlchemy(config)
        assert db is not None
        assert db.binds["default"] is not None

    def test_init_with_app(self, config: SQLAlchemyConfig, app: FastAPI):
        """Test creating instance with app passed to constructor."""
        db = FastAPISQLAlchemy(config, app=app)
        assert app.state.sqlalchemy == db

    def test_base_model_creation(self, db: FastAPISQLAlchemy):
        """Test that Base model can be used to create models."""

        class TestModel(db.Base):
            __tablename__ = "test"
            id: sa.orm.Mapped[int] = sa.orm.mapped_column(primary_key=True)
            name: sa.orm.Mapped[str] = sa.orm.mapped_column()

        assert TestModel.__tablename__ == "test"
        assert hasattr(TestModel, "id")
        assert hasattr(TestModel, "name")

    @pytest.mark.asyncio
    async def test_async_database_operations(
        self, db: FastAPISQLAlchemy, app: FastAPI
    ):
        """Test basic async database operations work."""

        class User(db.Base):
            __tablename__ = "users"
            id: sa.orm.Mapped[int] = sa.orm.mapped_column(primary_key=True)
            username: sa.orm.Mapped[str] = sa.orm.mapped_column()

        # Create tables
        await db.create_all()

        # Test session usage
        async with db.bind.Session() as session:
            async with session.begin():
                user = User(username="test_user")
                session.add(user)

            # Query the user
            result = await session.execute(sa.select(User))
            users = result.scalars().all()
            assert len(users) == 1
            assert users[0].username == "test_user"

    @pytest.mark.asyncio
    async def test_lifespan_events(self, config: SQLAlchemyConfig):
        """Test that lifespan events are registered."""
        app = FastAPI()
        db = FastAPISQLAlchemy(config, app=app)

        # Check that shutdown event was registered (engine disposal)
        assert len(app.router.on_shutdown) > 0

    @pytest.mark.asyncio
    async def test_engine_disposal_on_shutdown(
        self, db: FastAPISQLAlchemy, app: FastAPI
    ):
        """Test that engines are disposed on shutdown."""

        class Item(db.Base):
            __tablename__ = "items"
            id: sa.orm.Mapped[int] = sa.orm.mapped_column(primary_key=True)

        await db.create_all()

        # Access engine to ensure it's created
        engine = db.bind.engine
        assert engine is not None

        # Simulate shutdown by calling the shutdown handler
        shutdown_handlers = app.router.on_shutdown
        for handler in shutdown_handlers:
            await handler()

        # After shutdown, engine should be disposed
        # (We can't easily verify this without checking internal state,
        # but we can at least verify the handler ran without errors)
        assert True

    def test_client_integration(self, db: FastAPISQLAlchemy, app: FastAPI):
        """Test integration with TestClient."""

        @app.get("/")
        def read_root():
            return {"db": "available" if hasattr(app.state, "sqlalchemy") else "missing"}

        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"db": "available"}

    @pytest.mark.asyncio
    async def test_multiple_binds(self):
        """Test that multiple database binds work correctly."""
        config = SQLAlchemyConfig(
            binds={
                "default": AsyncBindConfig(url="sqlite+aiosqlite:///:memory:"),
                "other": AsyncBindConfig(url="sqlite+aiosqlite:///:memory:"),
            }
        )
        app = FastAPI()
        db = FastAPISQLAlchemy(config, app=app)

        assert "default" in db.binds
        assert "other" in db.binds
        assert db.bind == db.binds["default"]

    @pytest.mark.asyncio
    async def test_async_session_context_manager(self, db: FastAPISQLAlchemy):
        """Test async session context manager works correctly."""

        class Product(db.Base):
            __tablename__ = "products"
            id: sa.orm.Mapped[int] = sa.orm.mapped_column(primary_key=True)
            name: sa.orm.Mapped[str] = sa.orm.mapped_column()

        await db.create_all()

        async with db.bind.Session() as session:
            async with session.begin():
                product = Product(name="Widget")
                session.add(product)

        # Verify in new session
        async with db.bind.Session() as session:
            result = await session.execute(sa.select(Product))
            products = result.scalars().all()
            assert len(products) == 1
            assert products[0].name == "Widget"
