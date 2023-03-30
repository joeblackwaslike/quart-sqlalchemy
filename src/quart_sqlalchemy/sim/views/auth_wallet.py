import logging
import typing as t

from quart import Blueprint
from quart import g
from quart.utils import run_sync
from quart_schema.validation import validate

from ..model import WalletManagementType
from ..model import WalletType
from ..schema import BaseSchema
from ..util import ObjectID
from .decorator import authorized_request


logger = logging.getLogger(__name__)
api = Blueprint("auth_wallet", __name__, url_prefix="auth_wallet")


@api.before_request
def set_feature_owner():
    g.request_feature_owner = "wallet"


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


@authorized_request(authenticate_client=True, authenticate_user=True)
@validate(request=WalletSyncRequest, responses={200: (WalletSyncResponse, None)})
@api.route("/sync", methods=["POST"])
async def sync_auth_user_wallet(data: WalletSyncRequest):
    try:
        with g.bind.Session() as session:
            wallet = await run_sync(g.h.AuthWallet(session).sync_auth_wallet)(
                g.auth.user.id,
                data.public_address,
                data.encrypted_private_address,
                WalletManagementType.DELEGATED.value,
            )
    except RuntimeError:
        raise RuntimeError("Unsupported wallet type or network")

    return WalletSyncResponse(
        wallet_id=wallet.id,
        auth_user_id=wallet.auth_user_id,
        wallet_type=wallet.wallet_type,
        public_address=wallet.public_address,
        encrypted_private_address=wallet.encrypted_private_address,
    )
