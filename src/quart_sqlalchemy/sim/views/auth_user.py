import logging
import typing as t

import sqlalchemy.orm
from dependency_injector.wiring import inject
from dependency_injector.wiring import Provide

from quart_sqlalchemy.framework import QuartSQLAlchemy

from ..auth import authorized_request
from ..auth import RequestCredentials
from ..container import Container
from ..handle import AuthUserHandler
from ..model import EntityType
from ..schema import AuthUserSchema
from ..schema import BaseSchema
from ..schema import ResponseWrapper
from .util import APIBlueprint


sa = sqlalchemy

logger = logging.getLogger(__name__)
api = APIBlueprint("auth_user", __name__, url_prefix="/auth_user")


class CreateAuthUserRequest(BaseSchema):
    email: str


class CreateAuthUserResponse(BaseSchema):
    auth_user: AuthUserSchema


@api.get(
    "/",
    authorizer=authorized_request(
        [
            {
                "public-api-key": [],
                "session-token-bearer": [],
            }
        ],
    ),
)
@inject
def get_auth_user(
    auth_user_handler: AuthUserHandler = Provide["AuthUserHandler"],
    db: QuartSQLAlchemy = Provide["db"],
    credentials: RequestCredentials = Provide["request_credentials"],
) -> ResponseWrapper[AuthUserSchema]:
    with db.bind.Session() as session:
        auth_user = auth_user_handler.get_by_session_token(session, credentials.current_user.value)

    return ResponseWrapper[AuthUserSchema](data=AuthUserSchema.from_orm(auth_user))


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
def create_auth_user(
    data: CreateAuthUserRequest,
    auth_user_handler: AuthUserHandler = Provide["AuthUserHandler"],
    db: QuartSQLAlchemy = Provide["db"],
    credentials: RequestCredentials = Provide[Container.request_credentials],
) -> ResponseWrapper[CreateAuthUserResponse]:
    with db.bind.Session() as session:
        with session.begin():
            client = auth_user_handler.create_verified_user(
                session,
                email=data.email,
                client_id=credentials.current_client.subject.id,
                user_type=EntityType.MAGIC.value,
            )

    return ResponseWrapper[CreateAuthUserResponse](
        data=dict(auth_user=AuthUserSchema.from_orm(client))  # type: ignore
    )
