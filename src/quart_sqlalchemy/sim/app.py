import json
import logging
import re
import typing as t

import sqlalchemy as sa
from pydantic import BaseModel
from quart import g
from quart import Quart
from quart import request
from quart import Request
from quart import Response
from quart_schema import QuartSchema

from .. import Base
from .. import SQLAlchemyConfig
from ..framework import QuartSQLAlchemy
from .util import ObjectID


AUTHORIZATION_PATTERN = re.compile(r"Bearer (?P<token>.+)")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MyBase(Base):
    type_annotation_map = {ObjectID: sa.Integer}


app = Quart(__name__)
db = QuartSQLAlchemy(
    SQLAlchemyConfig.parse_obj(
        {
            "model_class": MyBase,
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
                    "engine": {
                        "url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"
                    },
                    "session": {"expire_on_commit": False},
                },
            },
        }
    )
)
openapi = QuartSchema(app)


class RequestAuth(BaseModel):
    client: t.Optional[t.Any] = None
    user: t.Optional[t.Any] = None

    @property
    def has_client(self):
        return self.client is not None

    @property
    def has_user(self):
        return self.user is not None

    @property
    def is_anonymous(self):
        return all([self.has_client is False, self.has_user is False])


def get_request_client(request: Request):
    api_key = request.headers.get("X-Public-API-Key")
    if not api_key:
        return

    with g.bind.Session() as session:
        try:
            magic_client = g.h.MagicClient(session).get_by_public_api_key(api_key)
        except ValueError:
            return
        else:
            return magic_client


def get_request_user(request: Request):
    auth_header = request.headers.get("Authorization")

    if not auth_header:
        return
    m = AUTHORIZATION_PATTERN.match(auth_header)
    if m is None:
        raise RuntimeError("invalid authorization header")

    auth_token = m.group("auth_token")

    with g.bind.Session() as session:
        try:
            auth_user = g.h.AuthUser(session).get_by_session_token(auth_token)
        except ValueError:
            return
        else:
            return auth_user


@app.before_request
def set_ethereum_network():
    g.request_network = request.headers.get("X-Fortmatic-Network", "GOERLI").upper()


@app.before_request
def set_bind_handlers_for_request():
    from quart_sqlalchemy.sim.handle import Handlers

    g.db = db

    method = request.method
    if method in ["GET", "OPTIONS", "TRACE", "HEAD"]:
        bind = "read-replica"
    else:
        bind = "default"

    g.bind = db.get_bind(bind)
    g.h = Handlers(g.bind)


@app.before_request
def set_request_auth():
    g.auth = RequestAuth(
        client=get_request_client(request),
        user=get_request_user(request),
    )


@app.after_request
async def add_json_response_envelope(response: Response) -> Response:
    if response.mimetype != "application/json":
        return response
    data = await response.get_json()
    payload = dict(status="ok", message="", data=data)
    response.set_data(json.dumps(payload))
    return response
