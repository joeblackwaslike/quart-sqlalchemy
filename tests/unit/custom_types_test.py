from datetime import UTC, datetime, timezone

import pytest
import sqlalchemy as sa
from pydantic import BaseModel
from sqlalchemy.orm import Mapped

from quart_sqlalchemy.model.custom_types import PydanticType, TZDateTime


class UserProfile(BaseModel):
    """Test Pydantic model for testing PydanticType."""

    username: str
    age: int
    is_active: bool = True


class TestPydanticType:
    def test_pydantic_type_save_and_load(self, db):
        """Test that PydanticType can save and load Pydantic models."""

        class TestModel(db.Base):
            __tablename__ = "test_pydantic_type"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            profile: Mapped[UserProfile] = sa.orm.mapped_column(PydanticType(UserProfile))

        db.create_all()

        # Create and save a model
        profile = UserProfile(username="alice", age=30, is_active=True)
        with db.bind.Session() as session:
            with session.begin():
                obj = TestModel(id=1, profile=profile)
                session.add(obj)
                session.flush()

        # Load it back
        with db.bind.Session() as session:
            loaded = session.get(TestModel, 1)
            assert loaded is not None
            assert isinstance(loaded.profile, UserProfile)
            assert loaded.profile.username == "alice"
            assert loaded.profile.age == 30
            assert loaded.profile.is_active is True

        db.drop_all()

    def test_pydantic_type_with_none(self, db):
        """Test that PydanticType handles None values."""

        class TestModelNone(db.Base):
            __tablename__ = "test_pydantic_none"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            profile: Mapped[UserProfile | None] = sa.orm.mapped_column(
                PydanticType(UserProfile), nullable=True
            )

        db.create_all()

        # Save with None
        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelNone(id=1, profile=None)
                session.add(obj)

        # Load it back
        with db.bind.Session() as session:
            loaded = session.get(TestModelNone, 1)
            assert loaded is not None
            assert loaded.profile is None

        db.drop_all()

    def test_pydantic_type_update(self, db):
        """Test that PydanticType can update existing models."""

        class TestModelUpdate(db.Base):
            __tablename__ = "test_pydantic_update"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            profile: Mapped[UserProfile] = sa.orm.mapped_column(PydanticType(UserProfile))

        db.create_all()

        # Create initial model
        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelUpdate(id=1, profile=UserProfile(username="alice", age=30))
                session.add(obj)

        # Update it
        with db.bind.Session() as session:
            with session.begin():
                obj = session.get(TestModelUpdate, 1)
                obj.profile = UserProfile(username="bob", age=25, is_active=False)

        # Verify update
        with db.bind.Session() as session:
            loaded = session.get(TestModelUpdate, 1)
            assert loaded.profile.username == "bob"
            assert loaded.profile.age == 25
            assert loaded.profile.is_active is False

        db.drop_all()

    def test_pydantic_type_model_dump(self):
        """Test that process_bind_param calls model_dump()."""
        pydantic_type = PydanticType(UserProfile)
        profile = UserProfile(username="test", age=20)

        # Mock dialect (not actually used in process_bind_param)
        result = pydantic_type.process_bind_param(profile, None)

        assert isinstance(result, dict)
        assert result == {"username": "test", "age": 20, "is_active": True}

    def test_pydantic_type_process_bind_param_with_none(self):
        """Test that process_bind_param handles None."""
        pydantic_type = PydanticType(UserProfile)
        result = pydantic_type.process_bind_param(None, None)
        assert result is None

    def test_pydantic_type_process_result_value(self):
        """Test that process_result_value deserializes correctly."""
        pydantic_type = PydanticType(UserProfile)
        data = {"username": "alice", "age": 30, "is_active": False}

        result = pydantic_type.process_result_value(data, None)

        assert isinstance(result, UserProfile)
        assert result.username == "alice"
        assert result.age == 30
        assert result.is_active is False

    def test_pydantic_type_process_result_value_with_none(self):
        """Test that process_result_value handles None."""
        pydantic_type = PydanticType(UserProfile)
        result = pydantic_type.process_result_value(None, None)
        assert result is None

    def test_pydantic_type_load_dialect_impl_postgresql(self):
        """Test that load_dialect_impl uses JSONB for PostgreSQL."""
        pydantic_type = PydanticType(UserProfile)

        # Mock PostgreSQL dialect
        class MockPostgresDialect:
            name = "postgresql"

            def type_descriptor(self, impl):
                return impl

        dialect = MockPostgresDialect()
        result = pydantic_type.load_dialect_impl(dialect)

        assert isinstance(result, sa.dialects.postgresql.JSONB)

    def test_pydantic_type_load_dialect_impl_other(self):
        """Test that load_dialect_impl uses JSON for non-PostgreSQL."""
        pydantic_type = PydanticType(UserProfile)

        # Mock SQLite dialect
        class MockSQLiteDialect:
            name = "sqlite"

            def type_descriptor(self, impl):
                return impl

        dialect = MockSQLiteDialect()
        result = pydantic_type.load_dialect_impl(dialect)

        assert isinstance(result, sa.JSON)


class TestTZDateTime:
    def test_tzdate_time_save_and_load(self, db):
        """Test that TZDateTime can save and load timezone-aware datetimes."""

        class TestModelTZDT(db.Base):
            __tablename__ = "test_tzdate_time"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            created_at: Mapped[datetime] = sa.orm.mapped_column(TZDateTime)

        db.create_all()

        # Create with UTC datetime
        now_utc = datetime.now(UTC)
        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelTZDT(id=1, created_at=now_utc)
                session.add(obj)

        # Load it back
        with db.bind.Session() as session:
            loaded = session.get(TestModelTZDT, 1)
            assert loaded is not None
            assert isinstance(loaded.created_at, datetime)
            assert loaded.created_at.tzinfo == UTC
            # Compare timestamps (allowing for microsecond differences)
            assert abs((loaded.created_at - now_utc).total_seconds()) < 1

        db.drop_all()

    def test_tzdate_time_converts_to_utc(self, db):
        """Test that TZDateTime converts non-UTC timezones to UTC."""

        class TestModelConvert(db.Base):
            __tablename__ = "test_tzdate_time_convert"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            timestamp: Mapped[datetime] = sa.orm.mapped_column(TZDateTime)

        db.create_all()

        # Create with Eastern timezone (UTC-5)
        from datetime import timedelta

        eastern = timezone(timedelta(hours=-5))  # UTC-5
        dt_eastern = datetime(2024, 1, 15, 12, 0, 0, tzinfo=eastern)

        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelConvert(id=1, timestamp=dt_eastern)
                session.add(obj)

        # Load it back - should be in UTC
        with db.bind.Session() as session:
            loaded = session.get(TestModelConvert, 1)
            assert loaded is not None
            assert loaded.timestamp.tzinfo == UTC
            # Should be converted to UTC (17:00 UTC = 12:00 UTC-5)
            assert loaded.timestamp.hour == 17

        db.drop_all()

    def test_tzdate_time_raises_on_naive_datetime(self):
        """Test that TZDateTime raises TypeError for naive datetime."""
        tzdt = TZDateTime()
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)

        with pytest.raises(TypeError, match="tzinfo is required"):
            tzdt.process_bind_param(naive_dt, None)

    def test_tzdate_time_process_bind_param_with_none(self):
        """Test that process_bind_param handles None."""
        tzdt = TZDateTime()
        result = tzdt.process_bind_param(None, None)
        assert result is None

    def test_tzdate_time_process_result_value_adds_utc(self):
        """Test that process_result_value adds UTC timezone."""
        tzdt = TZDateTime()
        # Simulate a datetime without timezone (from database)
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)

        result = tzdt.process_result_value(naive_dt, None)

        assert result is not None
        assert result.tzinfo == UTC
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_tzdate_time_process_result_value_with_none(self):
        """Test that process_result_value handles None."""
        tzdt = TZDateTime()
        result = tzdt.process_result_value(None, None)
        assert result is None

    def test_tzdate_time_python_type(self):
        """Test that python_type property returns datetime."""
        tzdt = TZDateTime()
        assert tzdt.python_type is datetime


@pytest.fixture(scope="module")
def db():
    """Provide a test database instance."""
    from quart import Quart

    from quart_sqlalchemy import SQLAlchemyConfig
    from quart_sqlalchemy.framework import QuartSQLAlchemy

    app = Quart(__name__)
    config = SQLAlchemyConfig(
        binds={
            "default": {
                "engine": {"url": "sqlite:///:memory:"},
                "session": {"expire_on_commit": False},
            }
        }
    )
    return QuartSQLAlchemy(config, app)
