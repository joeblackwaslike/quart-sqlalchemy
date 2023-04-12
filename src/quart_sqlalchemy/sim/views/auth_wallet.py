import logging
import typing as t

from dependency_injector.wiring import inject
from dependency_injector.wiring import Provide
from quart import g

from quart_sqlalchemy.framework import QuartSQLAlchemy

from ..auth import authorized_request
from ..auth import RequestCredentials
from ..handle import AuthWalletHandler
from ..model import WalletManagementType
from ..model import WalletType
from ..schema import BaseSchema
from ..schema import ResponseWrapper
from ..util import ObjectID
from ..web3 import Web3
from .util import APIBlueprint


logger = logging.getLogger(__name__)
api = APIBlueprint("auth_wallet", __name__, url_prefix="/auth_wallet")


@api.before_request
def set_feature_owner():
    g.request_feature_owner = "wallet-team"


class WalletSyncRequest(BaseSchema):
    public_address: str
    encrypted_private_address: str
    wallet_type: str
    hd_path: t.Optional[str] = None
    encrypted_seed_phrase: t.Optional[str] = None


class WalletSyncResponse(BaseSchema):
    wallet_id: ObjectID
    auth_user_id: ObjectID
    wallet_type: WalletType
    public_address: str
    encrypted_private_address: str


@api.post(
    "/sync",
    authorizer=authorized_request(
        [
            # We use the OpenAPI security scheme metadata to know which kind of authorization to enforce.
            #
            # Together in the same dict implies logical AND requirement so both public-api-key and
            # session-token will be enforced
            {
                "public-api-key": [],
                "session-token-bearer": [],
            }
        ],
    ),
)
@inject
def sync(
    data: WalletSyncRequest,
    auth_wallet_handler: AuthWalletHandler = Provide["AuthWalletHandler"],
    web3: Web3 = Provide["web3"],
    db: QuartSQLAlchemy = Provide["db"],
    credentials: RequestCredentials = Provide["request_credentials"],
) -> ResponseWrapper[WalletSyncResponse]:
    with db.bind.Session() as session:
        with session.begin():
            wallet = auth_wallet_handler.sync_auth_wallet(
                session,
                credentials.current_user.subject.id,
                data.public_address,
                data.encrypted_private_address,
                WalletManagementType.DELEGATED.value,
                network=web3.network,
                wallet_type=data.wallet_type,
            )

    return ResponseWrapper[WalletSyncResponse](
        data=dict(
            wallet_id=wallet.id,
            auth_user_id=wallet.auth_user_id,
            wallet_type=wallet.wallet_type,
            public_address=wallet.public_address,
            encrypted_private_address=wallet.encrypted_private_address,
        )  # type: ignore
    )
