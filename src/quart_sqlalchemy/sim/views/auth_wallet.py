import logging
import typing as t

from quart import g
from quart.utils import run_sync

from quart_sqlalchemy.retry import retry_context
from quart_sqlalchemy.retry import RetryError

from ..auth import authorized_request
from ..handle import AuthWalletHandler
from ..model import WalletManagementType
from ..model import WalletType
from ..schema import BaseSchema
from ..util import ObjectID
from .util import APIBlueprint


logger = logging.getLogger(__name__)
api = APIBlueprint("auth_wallet", __name__, url_prefix="auth_wallet")


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
async def sync(data: WalletSyncRequest) -> WalletSyncResponse:
    user_credential = g.authorized_credentials.get("session-token-bearer")

    try:
        for attempt in retry_context:
            with attempt:
                with g.bind.Session() as session:
                    wallet = AuthWalletHandler(g.network, session).sync_auth_wallet(
                        user_credential.subject.id,
                        data.public_address,
                        data.encrypted_private_address,
                        WalletManagementType.DELEGATED.value,
                    )
    except RetryError:
        pass
    except RuntimeError:
        raise RuntimeError("Unsupported wallet type or network")

    return WalletSyncResponse(
        wallet_id=wallet.id,
        auth_user_id=wallet.auth_user_id,
        wallet_type=wallet.wallet_type,
        public_address=wallet.public_address,
        encrypted_private_address=wallet.encrypted_private_address,
    )
