import typing as t

import sqlalchemy.orm
from dependency_injector import containers
from dependency_injector import providers
from quart import request

from quart_sqlalchemy.session import SessionProxy
from quart_sqlalchemy.sim.auth import RequestCredentials
from quart_sqlalchemy.sim.handle import AuthUserHandler
from quart_sqlalchemy.sim.handle import AuthWalletHandler
from quart_sqlalchemy.sim.handle import MagicClientHandler
from quart_sqlalchemy.sim.logic import LogicComponent

from .config import AppSettings
from .web3 import Web3
from .web3 import web3_node_factory


sa = sqlalchemy


def get_db_from_app(app):
    return app.extensions["sqlalchemy"]


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "quart_sqlalchemy.sim.views",
            "quart_sqlalchemy.sim.logic",
            "quart_sqlalchemy.sim.handle",
            "quart_sqlalchemy.sim.views.auth_wallet",
            "quart_sqlalchemy.sim.views.auth_user",
            "quart_sqlalchemy.sim.views.magic_client",
        ]
    )
    config = providers.Configuration(pydantic_settings=[AppSettings()])
    app = providers.Object()
    db = providers.Singleton(get_db_from_app, app=app)

    session_factory = providers.Singleton(SessionProxy)
    logic = providers.Singleton(LogicComponent)

    AuthUserHandler = providers.Singleton(AuthUserHandler)
    MagicClientHandler = providers.Singleton(MagicClientHandler)
    AuthWalletHandler = providers.Singleton(AuthWalletHandler)

    web3_node = providers.Singleton(web3_node_factory, config=config)
    web3 = providers.Singleton(
        Web3,
        node=web3_node,
        default_network=config.WEB3_DEFAULT_NETWORK,
        default_chain=config.WEB3_DEFAULT_CHAIN,
    )
    current_request = providers.Factory(lambda: request)
    request_credentials = providers.Singleton(RequestCredentials, request=current_request)
