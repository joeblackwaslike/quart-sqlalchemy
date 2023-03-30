import logging

from quart import Blueprint


logger = logging.getLogger(__name__)
api = Blueprint("auth_user", __name__, url_prefix="auth_user")
