import logging
import typing as t
from copy import deepcopy
from functools import wraps

from quart import g
from quart import Quart
from quart import request
from quart import Response
from quart.typing import ResponseReturnValue
from quart_schema import APIKeySecurityScheme
from quart_schema import HttpSecurityScheme
from quart_schema import QuartSchema
from werkzeug.utils import import_string


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


BLUEPRINTS = ("quart_sqlalchemy.sim.views.api",)
EXTENSIONS = (
    "quart_sqlalchemy.sim.db.db",
    "quart_sqlalchemy.sim.app.schema",
    "quart_sqlalchemy.sim.auth.auth",
)

DEFAULT_CONFIG = {
    "QUART_AUTH_SECURITY_SCHEMES": {
        "public-api-key": APIKeySecurityScheme(in_="header", name="X-Public-API-Key"),
        "session-token-bearer": HttpSecurityScheme(scheme="bearer", bearer_format="opaque"),
    },
    "REGISTER_BLUEPRINTS": ["quart_sqlalchemy.sim.views.api"],
}


schema = QuartSchema(security_schemes=DEFAULT_CONFIG["QUART_AUTH_SECURITY_SCHEMES"])


def wrap_response(func: t.Callable) -> t.Callable:
    @wraps(func)
    async def decorator(result: ResponseReturnValue) -> Response:
        # import pdb

        # pdb.set_trace()
        return await func(result)

    return decorator


def create_app(
    override_config: t.Optional[t.Dict[str, t.Any]] = None,
    extensions: t.Sequence[str] = EXTENSIONS,
    blueprints: t.Sequence[str] = BLUEPRINTS,
):
    override_config = override_config or {}

    config = deepcopy(DEFAULT_CONFIG)
    config.update(override_config)

    app = Quart(__name__)
    app.config.from_mapping(config)

    for path in extensions:
        extension = import_string(path)
        extension.init_app(app)

    for path in blueprints:
        bp = import_string(path)
        app.register_blueprint(bp)

    @app.before_request
    def set_ethereum_network():
        g.network = request.headers.get("X-Ethereum-Network", "GOERLI").upper()

    # app.make_response = wrap_response(app.make_response)

    return app


# @app.after_request
# async def add_json_response_envelope(response: Response) -> Response:
#     if response.mimetype != "application/json":
#         return response
#     data = await response.get_json()
#     payload = dict(status="ok", message="", data=data)
#     response.set_data(json.dumps(payload))
#     return response
