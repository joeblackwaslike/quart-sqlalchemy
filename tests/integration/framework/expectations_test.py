import logging

import pytest
import quart.flask_patch
from quart import Quart
from quart import signals
from starlette.testclient import TestClient


logger = logging.getLogger(__name__)

app = Quart(__name__)
app.config.from_mapping({"TESTING": True})

custom_signal = signals._signals.signal("custom-signal")


@app.before_request
async def on_before_request():
    print("hi from before request handler")
    events.append("on_before_request")


@app.route("/", methods=["GET"])
async def index():
    await custom_signal.send(1)
    return dict()


@custom_signal.connect
async def signal_handler(sender):
    print("hi from signal handler")
    events.append("signal_handler")


events = []


class TestTestClientExpectations:
    @pytest.fixture
    def events_manager(self):
        events.clear()
        yield events
        events.clear()

    @pytest.fixture
    def test_client(self):
        with TestClient(
            app,
            base_url="http://localhost",
            headers={"Content-Type": "application/json"},
        ) as client:
            yield client

    def test_starlette_test_client_fires_handlers(self, events_manager, test_client):
        response = test_client.get("/")
        assert response.status_code == 200

        assert "on_before_request" in events_manager
        assert "signal_handler" in events_manager
