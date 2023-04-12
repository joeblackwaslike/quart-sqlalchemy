import logging
import typing as t
from copy import deepcopy

from quart import Quart
from quart_schema import QuartSchema
from werkzeug.utils import import_string

from .config import settings
from .container import Container


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


schema = QuartSchema(security_schemes=settings.SECURITY_SCHEMES)


def create_app(override_config: t.Optional[t.Dict[str, t.Any]] = None):
    override_config = override_config or {}

    config = deepcopy(settings.dict())
    config.update(override_config)

    app = Quart(__name__)
    app.config.from_mapping(config)
    app.config.from_prefixed_env()

    for path in app.config["LOAD_EXTENSIONS"]:
        extension = import_string(path)
        extension.init_app(app)

    for path in app.config["LOAD_BLUEPRINTS"]:
        bp = import_string(path)
        app.register_blueprint(bp)

    container = Container(app=app)
    app.container = container

    return app
