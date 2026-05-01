import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Mapped

from quart_sqlalchemy.util import camel_to_snake_case, sqlachanges


class TestCamelToSnakeCase:
    def test_simple_camel_case(self):
        """Test simple CamelCase to snake_case conversion."""
        assert camel_to_snake_case("CamelCase") == "camel_case"

    def test_multiple_words(self):
        """Test multiple word conversion."""
        assert camel_to_snake_case("UserProfile") == "user_profile"
        assert camel_to_snake_case("HTTPResponse") == "http_response"

    def test_consecutive_capitals(self):
        """Test consecutive capital letters."""
        assert camel_to_snake_case("XMLParser") == "xml_parser"
        assert camel_to_snake_case("HTMLElement") == "html_element"

    def test_numbers_in_name(self):
        """Test names with numbers."""
        assert camel_to_snake_case("User2Profile") == "user2_profile"
        assert camel_to_snake_case("HTTP2Server") == "http2_server"

    def test_already_snake_case(self):
        """Test that snake_case remains unchanged."""
        assert camel_to_snake_case("already_snake") == "already_snake"
        assert camel_to_snake_case("user_profile") == "user_profile"

    def test_single_word(self):
        """Test single word (no conversion needed)."""
        assert camel_to_snake_case("user") == "user"
        assert camel_to_snake_case("User") == "user"

    def test_leading_capitals_stripped(self):
        """Test that leading underscores are stripped."""
        # The implementation strips leading underscores
        result = camel_to_snake_case("_PrivateClass")
        assert not result.startswith("_")


class TestSqlaChanges:
    def test_sqlachanges_with_modifications(self, db):
        """Test sqlachanges detects attribute modifications."""

        class TestModel(db.Base):
            __tablename__ = "test_sqlachanges"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            name: Mapped[str] = sa.orm.mapped_column()
            value: Mapped[int] = sa.orm.mapped_column()

        db.create_all()

        with db.bind.Session() as session:
            with session.begin():
                obj = TestModel(id=1, name="original", value=100)
                session.add(obj)
                session.flush()

                # Make changes
                obj.name = "modified"
                obj.value = 200

                changes = sqlachanges(obj)

                # Should have changes for name and value
                assert "name" in changes
                assert "value" in changes

                # Changes should show history: [old, new]
                assert changes["name"] == ["original", "modified"]
                assert changes["value"] == [100, 200]

        db.drop_all()

    def test_sqlachanges_no_modifications(self, db):
        """Test sqlachanges returns empty dict for unmodified object."""

        class TestModelNoMods(db.Base):
            __tablename__ = "test_sqlachanges_no_mods"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            name: Mapped[str] = sa.orm.mapped_column()

        db.create_all()

        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelNoMods(id=1, name="unchanged")
                session.add(obj)
                session.flush()

                # No changes made
                changes = sqlachanges(obj)
                assert changes == {}

        db.drop_all()

    def test_sqlachanges_multiple_changes_to_same_attribute(self, db):
        """Test sqlachanges tracks changes to same attribute (original and current)."""

        class TestModelMultiple(db.Base):
            __tablename__ = "test_sqlachanges_multiple"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            counter: Mapped[int] = sa.orm.mapped_column()

        db.create_all()

        with db.bind.Session() as session:
            with session.begin():
                obj = TestModelMultiple(id=1, counter=0)
                session.add(obj)
                session.flush()

                # Make multiple changes
                obj.counter = 1
                obj.counter = 2
                obj.counter = 3

                changes = sqlachanges(obj)

                # Should track changes
                assert "counter" in changes
                # SQLAlchemy history tracks original and current value: [0, 3]
                # (intermediate values are not tracked)
                assert changes["counter"] == [0, 3]

        db.drop_all()


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
