from quart import Blueprint
from quart import g

from .auth_user import api as auth_user_api
from .auth_wallet import api as auth_wallet_api
from .magic_client import api as magic_client_api


api = Blueprint("api", __name__, url_prefix="/api")

api.register_blueprint(auth_user_api)
api.register_blueprint(auth_wallet_api)
api.register_blueprint(magic_client_api)


@api.before_request
def set_feature_owner():
    g.request_feature_owner = "auth-team"
