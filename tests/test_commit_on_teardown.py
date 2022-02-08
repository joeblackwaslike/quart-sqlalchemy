import pytest
import quart


@pytest.fixture
def client(app, db, Todo):
    app.testing = False
    app.config["SQLALCHEMY_COMMIT_ON_TEARDOWN"] = True

    @app.route("/")
    async def index():
        return "\n".join(x.title for x in Todo.query.all())

    @app.route("/create", methods=["POST"])
    async def create():
        db.session.add(Todo("Test one", "test"))
        data = await quart.request.get_json() or {}

        if data.get("fail"):
            raise RuntimeError("Failing as requested")
        return "ok"

    return app.test_client()


async def test_commit_on_success(client):
    with pytest.warns(DeprecationWarning, match="COMMIT_ON_TEARDOWN"):
        async with client.app.app_context():
            resp = await client.post("/create")

    assert resp.status_code == 200

    resp = await client.get("/")
    assert (await resp.get_data()) == b"Test one"


@pytest.mark.xfail
async def test_roll_back_on_failure(client, db, Todo):
    with pytest.warns(DeprecationWarning, match="COMMIT_ON_TEARDOWN"):
        async with client.app.app_context():
            resp = await client.post("/create", json={"fail": "on"})

    assert resp.status_code == 500

    async with client.app.app_context():
        resp = await client.get("/")

    assert (await resp.get_data()) == b""
