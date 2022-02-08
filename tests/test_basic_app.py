import quart

from quart_sqlalchemy import get_debug_queries
from quart_sqlalchemy import SQLAlchemy


async def test_basic_insert(app, db, Todo):
    @app.route("/")
    async def index():
        return "\n".join(o.title for o in Todo.query.all())

    @app.route("/add", methods=["POST"])
    async def add():
        data = await quart.request.get_json()
        todo = Todo(data["title"], data["text"])
        db.session.add(todo)
        db.session.commit()
        return "added"

    client = app.test_client()
    async with app.app_context():
        await client.post("/add", json=dict(title="First Item", text="The text"))
        await client.post("/add", json=dict(title="2nd Item", text="The text"))
        rv = await client.get("/")

    assert await rv.get_data() == b"First Item\n2nd Item"


async def test_query_recording(app, db, Todo):
    async with app.test_request_context("/"):
        todo = Todo("Test 1", "test")
        db.session.add(todo)
        db.session.flush()
        todo.done = True
        db.session.commit()

        queries = get_debug_queries()
        assert len(queries) == 2

        query = queries[0]
        assert "insert into" in query.statement.lower()
        assert query.parameters[0] == "Test 1"
        assert query.parameters[1] == "test"
        assert "test_basic_app.py" in query.context
        assert "test_query_recording" in query.context

        query = queries[1]
        assert "update" in query.statement.lower()
        assert query.parameters[0] == 1
        assert query.parameters[1] == 1


def test_helper_api(db):
    assert db.metadata == db.Model.metadata


async def test_persist_selectable(app, db, Todo, recwarn):
    """In SA 1.3, mapper.mapped_table should be replaced with
    mapper.persist_selectable.
    """
    async with app.test_request_context("/"):
        todo = Todo("Test 1", "test")
        db.session.add(todo)
        db.session.commit()

    assert len(recwarn) == 0


def test_sqlite_relative_path(app, tmp_path):
    """If a SQLite URI has a relative path, it should be relative to the
    instance path, and that directory should be created.
    """
    app.instance_path = tmp_path / "instance"

    # tests default to memory, shouldn't create
    SQLAlchemy(app).get_engine()
    assert not app.instance_path.exists()

    # absolute path, shouldn't create
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:////tmp/test.sqlite"
    SQLAlchemy(app).get_engine()
    assert not app.instance_path.exists()

    # relative path, should create
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.sqlite"
    SQLAlchemy(app).get_engine()
    assert app.instance_path.exists()
