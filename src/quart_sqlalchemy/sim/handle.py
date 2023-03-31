import logging
import typing as t
from datetime import datetime

from sqlalchemy.orm import Session

from quart_sqlalchemy.sim.logic import LogicComponent as Logic
from quart_sqlalchemy.sim.model import AuthUser
from quart_sqlalchemy.sim.model import AuthWallet
from quart_sqlalchemy.sim.model import EntityType
from quart_sqlalchemy.sim.model import WalletType
from quart_sqlalchemy.sim.util import ObjectID


logger = logging.getLogger(__name__)

CLIENTS_PER_API_USER_LIMIT = 50


class MaxClientsExceeded(Exception):
    pass


class AuthUserBaseError(Exception):
    pass


class InvalidSubstringError(AuthUserBaseError):
    pass


class APIKeySet(t.NamedTuple):
    public_key: str
    secret_key: str


class HandlerBase:
    logic: Logic
    session: Session
    """The base class for all handler classes. It provides handler with access
    to our logic object.
    """

    def __init__(self, session: t.Optional[Session], logic: t.Optional[Logic] = None):
        self.session = session
        self.logic = logic or Logic()


def get_product_type_by_client_id(client_id):
    return EntityType.MAGIC.value


class MagicClientHandler(HandlerBase):
    def add(
        self,
        magic_api_user_id,
        magic_team_id,
        app_name=None,
        is_magic_connect_enabled=False,
    ):
        """Registers a new client.

        Args:
            is_magic_connect_enabled (boolean): if True, it will create a Magic Connect app.

        Returns:
            A ``MagicClient``.
        """
        magic_clients_count = self.logic.MagicClientAPIUser.count_by_magic_api_user_id(
            self.session,
            magic_api_user_id,
        )

        if magic_clients_count >= CLIENTS_PER_API_USER_LIMIT:
            raise MaxClientsExceeded()

        return self.add_client(
            magic_api_user_id,
            magic_team_id,
            app_name,
            is_magic_connect_enabled,
        )

    def get_by_public_api_key(self, public_api_key):
        return self.logic.MagicClientAPIKey.get_by_public_api_key(self.session, public_api_key)

    def add_client(
        self,
        magic_api_user_id,
        magic_team_id,
        app_name=None,
        is_magic_connect_enabled=False,
    ):
        live_api_key = APIKeySet(public_key="xxx", secret_key="yyy")

        # with self.logic.begin(ro=False) as session:
        return self.logic.MagicClient._add(
            self.session,
            app_name=app_name,
        )

        # self.logic.MagicClientAPIKey._add(
        #     session,
        #     magic_client.id,
        #     live_api_key_pair=live_api_key,
        # )
        # self.logic.MagicClientAPIUser._add(
        #     session,
        #     magic_api_user_id,
        #     magic_client.id,
        # )

        # self.logic.MagicClientAuthMethods._add(
        #     session,
        #     magic_client_id=magic_client.id,
        #     is_magic_connect_enabled=is_magic_connect_enabled,
        #     is_metamask_wallet_enabled=(True if is_magic_connect_enabled else False),
        #     is_wallet_connect_enabled=(True if is_magic_connect_enabled else False),
        #     is_coinbase_wallet_enabled=(True if is_magic_connect_enabled else False),
        # )

        # self.logic.MagicClientTeam._add(session, magic_client.id, magic_team_id)

        # return magic_client, live_api_key

    def get_magic_api_user_id_by_client_id(self, magic_client_id):
        return self.logic.MagicClient.get_magic_api_user_id_by_client_id(
            self.session, magic_client_id
        )

    def get_by_id(self, magic_client_id):
        return self.logic.MagicClient.get_by_id(self.session, magic_client_id)

    def update_app_name_by_id(self, magic_client_id, app_name):
        """
        Args:
            magic_client_id (ObjectID|int|str): self explanatory.
            app_name (str): Desired application name.

        Returns:
            None if `magic_client_id` doesn't exist in the db
            app_name if update was successful
        """
        client = self.logic.MagicClient.update_by_id(
            self.session, magic_client_id, app_name=app_name
        )

        if not client:
            return None

        return client.app_name

    def update_by_id(self, magic_client_id, **kwargs):
        client = self.logic.MagicClient.update_by_id(self.session, magic_client_id, **kwargs)

        return client

    def set_inactive_by_id(self, magic_client_id):
        """
        Args:
            magic_client_id (ObjectID|int|str): self explanatory.

        Returns:
            None
        """
        self.logic.MagicClient.update_by_id(self.session, magic_client_id, is_active=False)

    def get_users_for_client(
        self,
        magic_client_id,
        offset=None,
        limit=None,
        include_count=False,
    ):
        """
        Returns emails and signup timestamps for all auth users belonging to a given client
        """
        auth_user_handler = AuthUserHandler(session=self.session)
        product_type = get_product_type_by_client_id(magic_client_id)
        auth_users = auth_user_handler.get_by_client_id_and_user_type(
            magic_client_id,
            product_type,
            offset=offset,
            limit=limit,
        )

        # Here we blindly load from oauth users table because we only provide
        # two login methods right now. If not email link then it is oauth.
        # TODO(ajen#ch22926|2020-08-14): rely on the `login_method` column to
        # deterministically load from correct source (oauth, webauthn, etc.).
        # emails_from_oauth = OAuthUserHandler().get_emails_by_auth_user_ids(
        #     [auth_user.id for auth_user in auth_users if auth_user.email is None],
        # )

        data = {
            "users": [
                dict(email=u.email or "none", signup_ts=int(datetime.timestamp(u.time_created)))
                for u in auth_users
            ]
        }

        if include_count:
            data["count"] = auth_user_handler.get_user_count_by_client_id_and_user_type(
                magic_client_id,
                product_type,
            )

        return data

    def get_users_for_client_v2(
        self,
        magic_client_id,
        offset=None,
        limit=None,
        include_count=False,
    ):
        """
        Returns emails, signup timestamps, provenance and MFA enablement for all auth users
        belonging to a given client.
        """
        auth_user_handler = AuthUserHandler(session=self.session)
        product_type = get_product_type_by_client_id(magic_client_id)
        auth_users = auth_user_handler.get_by_client_id_and_user_type(
            magic_client_id,
            product_type,
            offset=offset,
            limit=limit,
        )

        data = {
            "users": [
                dict(email=u.email or "none", signup_ts=int(datetime.timestamp(u.time_created)))
                for u in auth_users
            ]
        }

        if include_count:
            data["count"] = auth_user_handler.get_user_count_by_client_id_and_user_type(
                magic_client_id,
                product_type,
            )

        return data

    # def get_user_logins_for_client(self, magic_client_id, limit=None):
    #     logins = AuthUserLoginHandler().get_logins_by_magic_client_id(
    #         magic_client_id,
    #         limit=limit or 20,
    #     )
    #     user_logins = get_user_logins_response(logins)

    #     return sorted(
    #         user_logins,
    #         key=lambda x: x["login_ts"],
    #         reverse=True,
    #     )[:limit]


class AuthUserHandler(HandlerBase):
    # auth_user_mfa_handler: AuthUserMfaHandler

    def __init__(self, *args, auth_user_mfa_handler=None, **kwargs):
        super().__init__(*args, **kwargs)
        # self.auth_user_mfa_handler = auth_user_mfa_handler or AuthUserMfaHandler()

    def get_by_session_token(self, session_token):
        return self.logic.AuthUser.get_by_session_token(self.session, session_token)

    def get_or_create_by_email_and_client_id(
        self,
        email,
        client_id,
        user_type=EntityType.MAGIC.value,
    ):
        auth_user = self.logic.AuthUser.get_by_email_and_client_id(
            self.session,
            email,
            client_id,
            user_type=user_type,
        )
        if not auth_user:
            # try:
            #     email = enhanced_email_validation(
            #         email,
            #         source=MAGIC,
            #         # So we don't affect sign-up.
            #         silence_network_error=True,
            #     )
            # except (
            #     EnhanceEmailValidationError,
            #     EnhanceEmailSuggestionError,
            # ) as e:
            #     logger.warning(
            #         "Email Start Attempt.",
            #         exc_info=True,
            #     )
            #     raise EnhancedEmailValidation(error_message=str(e)) from e

            auth_user = self.logic.AuthUser.add_by_email_and_client_id(
                self.session,
                client_id,
                email=email,
                user_type=user_type,
            )
        return auth_user

    def get_by_id_and_validate_exists(self, auth_user_id):
        """This function helps formalize how a non-existent auth user should be handled."""
        auth_user = self.logic.AuthUser.get_by_id(self.session, auth_user_id)
        if auth_user is None:
            raise RuntimeError('resource_name="auth_user"')
        return auth_user

    # This function is reserved for consolidating into a canonical user. Do not
    # call this function under other circumstances as it will automatically set
    # the user as verified. See ch-25343 for additional details.
    def create_verified_user(
        self,
        client_id,
        email,
        user_type=EntityType.FORTMATIC.value,
    ):
        # with self.logic.begin(ro=False) as session:
        auid = self.logic.AuthUser._add_by_email_and_client_id(
            self.session,
            client_id,
            email,
            user_type=user_type,
        ).id
        auth_user = self.logic.AuthUser._update_by_id(
            self.session,
            auid,
            date_verified=datetime.utcnow(),
        )

        return auth_user

    # def get_auth_user_from_public_address(self, public_address):
    #     wallet = self.logic.AuthWallet.get_by_public_address(public_address)

    #     if not wallet:
    #         return None

    #     return self.logic.AuthUser.get_by_id(wallet.auth_user_id)

    def get_by_id(self, auth_user_id, load_mfa_methods=False) -> AuthUser:
        # join_list = ["mfa_methods"] if load_mfa_methods else None
        return self.logic.AuthUser.get_by_id(self.session, auth_user_id)

    def get_by_client_id_and_user_type(
        self,
        client_id,
        user_type,
        offset=None,
        limit=None,
    ):
        if user_type == EntityType.CONNECT.value:
            return self.logic.AuthUser.get_by_client_id_for_connect(
                self.session,
                client_id,
                offset=offset,
                limit=limit,
            )
        else:
            return self.logic.AuthUser.get_by_client_id_and_user_type(
                self.session,
                client_id,
                user_type,
                offset=offset,
                limit=limit,
            )

    def get_by_client_ids_and_user_type(
        self,
        client_ids,
        user_type,
        offset=None,
        limit=None,
    ):
        return self.logic.AuthUser.get_by_client_ids_and_user_type(
            self.session,
            client_ids,
            user_type,
            offset=offset,
            limit=limit,
        )

    def get_user_count_by_client_id_and_user_type(self, client_id, user_type):
        if user_type == EntityType.CONNECT.value:
            return self.logic.AuthUser.get_user_count_by_client_id_for_connect(
                self.session,
                client_id,
            )
        else:
            return self.logic.AuthUser.get_user_count_by_client_id_and_user_type(
                self.session,
                client_id,
                user_type,
            )

    def exist_by_email_client_id_and_user_type(self, email, client_id, user_type):
        return self.logic.AuthUser.exist_by_email_and_client_id(
            self.session,
            email,
            client_id,
            user_type=user_type,
        )

    def update_email_by_id(self, model_id, email):
        return self.logic.AuthUser.update_by_id(self.session, model_id, email=email)

    def update_phone_number_by_id(self, model_id, phone_number):
        return self.logic.AuthUser.update_by_id(self.session, model_id, phone_number=phone_number)

    def get_by_email_client_id_and_user_type(self, email, client_id, user_type):
        return self.logic.AuthUser.get_by_email_and_client_id(
            self.session,
            email,
            client_id,
            user_type,
        )

    def mark_date_verified_by_id(self, model_id):
        return self.logic.AuthUser.update_by_id(
            self.session,
            model_id,
            date_verified=datetime.utcnow(),
        )

    def set_role_by_email_magic_client_id(self, email, magic_client_id, role):
        auth_user = self.logic.AuthUser.get_by_email_and_client_id(
            self.session,
            email,
            magic_client_id,
            EntityType.MAGIC.value,
        )

        if not auth_user:
            auth_user = self.logic.AuthUser.add_by_email_and_client_id(
                self.session,
                magic_client_id,
                email,
                user_type=EntityType.MAGIC.value,
            )

        return self.logic.AuthUser.update_by_id(self.session, auth_user.id, **{role: True})

    def search_by_client_id_and_substring(
        self,
        client_id,
        substring,
        offset=None,
        limit=10,
        load_mfa_methods=False,
    ):
        # join_list = ["mfa_methods"] if load_mfa_methods is True else None

        if not isinstance(substring, str) or len(substring) < 3:
            raise InvalidSubstringError()

        auth_users = self.logic.AuthUser.get_by_client_id_with_substring_search(
            self.session,
            client_id,
            substring,
            offset=offset,
            limit=limit,
            # join_list=join_list,
        )

        # mfa_enablements = self.auth_user_mfa_handler.is_active_batch(
        #     [auth_user.id for auth_user in auth_users],
        # )
        # for auth_user in auth_users:
        #     if mfa_enablements[auth_user.id] is False:
        #         auth_user.mfa_methods = []

        return auth_users

    def is_magic_connect_enabled(self, auth_user_id=None, auth_user=None):
        if auth_user is None and auth_user_id is None:
            raise Exception("At least one argument needed: auth_user_id or auth_user.")

        if auth_user is None:
            auth_user = self.get_by_id(auth_user_id)

        return auth_user.user_type == EntityType.CONNECT.value

    def mark_as_inactive(self, auth_user_id):
        self.logic.AuthUser.update_by_id(self.session, auth_user_id, is_active=False)

    def get_by_email_and_wallet_type_for_interop(self, email, wallet_type, network):
        """
        Opinionated method for fetching AuthWallets by email address, wallet_type and network.
        """
        return self.logic.AuthUser.get_by_email_for_interop(
            email=email,
            wallet_type=wallet_type,
            network=network,
        )

    def get_magic_connect_auth_user(self, auth_user_id):
        auth_user = self.get_by_id_and_validate_exists(auth_user_id)
        if not auth_user.is_magic_connect_user:
            raise RuntimeError("RequestForbidden")
        return auth_user


# @signals.auth_user_duplicate.connect
# def handle_duplicate_auth_users(
#     current_app,
#     original_auth_user_id,
#     duplicate_auth_user_ids,
#     auth_user_handler: t.Optional[AuthUserHandler] = None,
# ) -> None:
#     logger.info(f"{len(duplicate_auth_user_ids)} dupe(s) found for {original_auth_user_id}")

#     auth_user_handler = auth_user_handler or AuthUserHandler()

#     for dupe_id in duplicate_auth_user_ids:
#         logger.info(
#             f"marking auth_user_id {dupe_id} as inactive, in favor of original {original_auth_user_id}",
#         )
#         auth_user_handler.mark_as_inactive(dupe_id)


class AuthWalletHandler(HandlerBase):
    # account_linking_feature = LDFeatureFlag("is-account-linking-enabled", anonymous_user=True)

    def __init__(self, network, *args, wallet_type=WalletType.ETH, **kwargs):
        super().__init__(*args, **kwargs)
        self.wallet_network = network
        self.wallet_type = wallet_type

    def get_by_id(self, model_id):
        return self.logic.AuthWallet.get_by_id(self.session, model_id)

    def get_by_public_address(self, public_address):
        return self.logic.AuthWallet.get_by_public_address(self.session, public_address)

    def get_by_auth_user_id(
        self,
        auth_user_id: ObjectID,
        network: t.Optional[str] = None,
        wallet_type: t.Optional[WalletType] = None,
        **kwargs,
    ) -> t.List[AuthWallet]:
        auth_user = self.logic.AuthUser.get_by_id(
            self.session,
            auth_user_id,
            join_list=["linked_primary_auth_user"],
        )

        if auth_user.has_linked_primary_auth_user:
            logger.info(
                "Linked primary_auth_user found for wallet delegation",
                extra=dict(
                    auth_user_id=auth_user.id,
                    delegated_to=auth_user.linked_primary_auth_user_id,
                ),
            )
            auth_user = auth_user.linked_primary_auth_user

        return self.logic.AuthWallet.get_by_auth_user_id(
            self.session,
            auth_user.id,
            network=network,
            wallet_type=wallet_type,
            **kwargs,
        )

    def sync_auth_wallet(
        self,
        auth_user_id,
        public_address,
        encrypted_private_address,
        wallet_management_type,
    ):
        existing_wallet = self.logic.AuthWallet.get_by_auth_user_id(
            self.session,
            auth_user_id,
        )
        if existing_wallet:
            raise RuntimeError("WalletExistsForNetworkAndWalletType")

        return self.logic.AuthWallet.add(
            self.session,
            public_address,
            encrypted_private_address,
            self.wallet_type,
            self.wallet_network,
            management_type=wallet_management_type,
            auth_user_id=auth_user_id,
        )
