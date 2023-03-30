import logging

from quart import Blueprint


logger = logging.getLogger(__name__)
api = Blueprint("magic_client", __name__, url_prefix="magic_client")
