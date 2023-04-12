import logging
import typing as t

from dependency_injector.wiring import inject
from dependency_injector.wiring import Provide

from quart_sqlalchemy.framework import QuartSQLAlchemy
from quart_sqlalchemy.session import set_global_contextual_session

from ..auth import authorized_request
from ..auth import RequestCredentials
from ..handle import MagicClientHandler
from ..model import ConnectInteropStatus
from ..schema import BaseSchema
from ..schema import MagicClientSchema
from ..schema import ResponseWrapper
from .util import APIBlueprint


logger = logging.getLogger(__name__)
api = APIBlueprint("magic_client", __name__, url_prefix="/magic_client")


class CreateMagicClientRequest(BaseSchema):
    app_name: str
    rate_limit_tier: t.Optional[str] = None
    connect_interop: t.Optional[ConnectInteropStatus] = None
    is_signing_modal_enabled: bool = False
    global_audience_enabled: bool = False


class CreateMagicClientResponse(BaseSchema):
    magic_client: MagicClientSchema


@api.post(
    "/",
    authorizer=authorized_request(
        [
            {
                "public-api-key": [],
            }
        ],
    ),
)
@inject
def create_magic_client(
    data: CreateMagicClientRequest,
    magic_client_handler: MagicClientHandler = Provide["MagicClientHandler"],
    db: QuartSQLAlchemy = Provide["db"],
) -> ResponseWrapper[CreateMagicClientResponse]:
    with db.bind.Session() as session:
        with session.begin():
            with set_global_contextual_session(session):
                client = magic_client_handler.add(
                    app_name=data.app_name,
                    rate_limit_tier=data.rate_limit_tier,
                    connect_interop=data.connect_interop,
                    is_signing_modal_enabled=data.is_signing_modal_enabled,
                    global_audience_enabled=data.global_audience_enabled,
                )

    return ResponseWrapper[CreateMagicClientResponse](
        data=dict(magic_client=MagicClientSchema.from_orm(client))  # type: ignore
    )


@api.get(
    "/",
    authorizer=authorized_request(
        [
            {
                "public-api-key": [],
            }
        ],
    ),
)
@inject
def get_magic_client(
    magic_client_handler: MagicClientHandler = Provide["MagicClientHandler"],
    credentials: RequestCredentials = Provide["request_credentials"],
    db: QuartSQLAlchemy = Provide["db"],
) -> ResponseWrapper[MagicClientSchema]:
    with db.bind.Session() as session:
        with set_global_contextual_session(session):
            client = magic_client_handler.get_by_public_api_key(credentials.current_client.value)

    return ResponseWrapper[MagicClientSchema](
        data=MagicClientSchema.from_orm(client)  # type: ignore
    )
