from __future__ import annotations

import logging
import secrets
import typing as t
from datetime import datetime

import sqlalchemy
from dependency_injector.wiring import Provide
from quart import Quart

from quart_sqlalchemy.session import SessionProxy
from quart_sqlalchemy.sim import signals
from quart_sqlalchemy.sim.logic import LogicComponent
from quart_sqlalchemy.sim.model import AuthUser
from quart_sqlalchemy.sim.model import AuthWallet
from quart_sqlalchemy.sim.model import EntityType
from quart_sqlalchemy.sim.model import WalletType
from quart_sqlalchemy.sim.util import ObjectID


sa = sqlalchemy

logger = logging.getLogger(__name__)

CLIENTS_PER_API_USER_LIMIT = 50


def get_product_type_by_client_id(_):
    return EntityType.MAGIC.value


class MaxClientsExceeded(Exception):
    pass


class AuthUserBaseError(Exception):
    pass


class InvalidSubstringError(AuthUserBaseError):
    pass


class HandlerBase:
    logic: LogicComponent = Provide["logic"]
    session_factory = SessionProxy()


class MagicClientHandler(HandlerBase):
    auth_user_handler: AuthUserHandler = Provide["AuthUserHandler"]

    def add(
        self,
        app_name=None,
        rate_limit_tier=None,
        connect_interop=None,
        is_signing_modal_enabled=False,
        global_audience_enabled=False,
    ):
        """Registers a new client.

        Args:
            is_magic_connect_enabled (boolean): if True, it will create a Magic Connect app.

        Returns:
            A ``MagicClient``.
        """

        return self.logic.MagicClient.add(
            self.session_factory(),
            app_name=app_name,
            rate_limit_tier=rate_limit_tier,
            connect_interop=connect_interop,
            is_signing_modal_enabled=is_signing_modal_enabled,
            global_audience_enabled=global_audience_enabled,
        )

    def get_by_public_api_key(self, public_api_key):
        return self.logic.MagicClient.get_by_public_api_key(self.session_factory(), public_api_key)

    def get_by_id(self, magic_client_id):
        return self.logic.MagicClient.get_by_id(self.session_factory(), magic_client_id)

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
            self.session_factory(), magic_client_id, app_name=app_name
        )

        return client.app_name if client else None

    def update_by_id(self, magic_client_id, **kwargs):
        return self.logic.MagicClient.update_by_id(
            self.session_factory(), magic_client_id, **kwargs
        )

    def set_inactive_by_id(self, magic_client_id):
        """
        Args:
            magic_client_id (ObjectID|int|str): self explanatory.

        Returns:
            None
        """
        self.logic.MagicClient.update_by_id(
            self.session_factory(), magic_client_id, is_active=False
        )

    def get_users_for_client(
        self,
        magic_client_id,
        offset=None,
        limit=None,
    ):
        """
        Returns emails and signup timestamps for all auth users belonging to a given client
        """
        product_type = get_product_type_by_client_id(magic_client_id)
        auth_users = self.auth_user_handler.get_by_client_id_and_user_type(
            magic_client_id,
            product_type,
            offset=offset,
            limit=limit,
        )

        return {
            "users": [
                dict(email=u.email or "none", signup_ts=int(datetime.timestamp(u.time_created)))
                for u in auth_users
            ]
        }


class AuthUserHandler(HandlerBase):
    def get_by_session_token(self, session_token):
        return self.logic.AuthUser.get_by_session_token(self.session_factory(), session_token)

    def get_or_create_by_email_and_client_id(
        self,
        email,
        client_id,
        user_type=EntityType.MAGIC.value,
    ):
        session = self.session_factory()
        with session.begin_nested():
            auth_user = self.logic.AuthUser.get_by_email_and_client_id(
                session,
                email,
                client_id,
                user_type=user_type,
                for_update=True,
            )
            if not auth_user:
                auth_user = self.logic.AuthUser.add_by_email_and_client_id(
                    session,
                    client_id,
                    email=email,
                    user_type=user_type,
                )
        return auth_user

    def create_verified_user(
        self,
        client_id,
        email,
        user_type=EntityType.FORTMATIC.value,
        **kwargs,
    ):
        session = self.session_factory()
        with session.begin_nested():
            auid = self.logic.AuthUser.add_by_email_and_client_id(
                session,
                client_id,
                email,
                user_type=user_type,
                **kwargs,
            ).id

            session.flush()

            auth_user = self.logic.AuthUser.update_by_id(
                session,
                auid,
                date_verified=datetime.utcnow(),
                current_session_token=secrets.token_hex(16),
            )

        return auth_user

    def get_by_id(self, auth_user_id) -> AuthUser:
        return self.logic.AuthUser.get_by_id(self.session_factory(), auth_user_id)

    def get_by_client_id_and_user_type(
        self,
        client_id,
        user_type,
        offset=None,
        limit=None,
    ):
        return self.logic.AuthUser.get_by_client_id_and_user_type(
            self.session_factory(),
            client_id,
            user_type,
            offset=offset,
            limit=limit,
        )

    def exist_by_email_client_id_and_user_type(self, email, client_id, user_type):
        return self.logic.AuthUser.exist_by_email_and_client_id(
            self.session_factory(),
            email,
            client_id,
            user_type=user_type,
        )

    def update_email_by_id(self, model_id, email):
        return self.logic.AuthUser.update_by_id(self.session_factory(), model_id, email=email)

    def get_by_email_client_id_and_user_type(self, email, client_id, user_type):
        return self.logic.AuthUser.get_by_email_and_client_id(
            self.session_factory(),
            email,
            client_id,
            user_type,
        )

    def mark_date_verified_by_id(self, model_id):
        return self.logic.AuthUser.update_by_id(
            self.session_factory(),
            model_id,
            date_verified=datetime.utcnow(),
        )

    def set_role_by_email_magic_client_id(self, email, magic_client_id, role):
        session = self.session_factory()
        auth_user = self.logic.AuthUser.get_by_email_and_client_id(
            session,
            email,
            magic_client_id,
            EntityType.MAGIC.value,
            for_update=True,
        )

        if not auth_user:
            auth_user = self.logic.AuthUser.add_by_email_and_client_id(
                session,
                magic_client_id,
                email,
                user_type=EntityType.MAGIC.value,
            )

        session.flush()

        return self.logic.AuthUser.update_by_id(session, auth_user.id, **{role: True})

    def mark_as_inactive(self, auth_user_id):
        self.logic.AuthUser.update_by_id(self.session_factory(), auth_user_id, is_active=False)


@signals.auth_user_duplicate.connect
def handle_duplicate_auth_users(
    app: Quart,
    original_auth_user_id: ObjectID,
    duplicate_auth_user_ids: t.Sequence[ObjectID],
) -> None:
    for dupe_id in duplicate_auth_user_ids:
        app.container.logic().AuthUser.update_by_id(dupe_id, is_active=False)


class AuthWalletHandler(HandlerBase):
    def get_by_id(self, model_id):
        return self.logic.AuthWallet.get_by_id(self.session_factory(), model_id)

    def get_by_public_address(self, public_address):
        return self.logic.AuthWallet().get_by_public_address(self.session_factory(), public_address)

    def get_by_auth_user_id(
        self,
        auth_user_id: ObjectID,
        network: t.Optional[str] = None,
        wallet_type: t.Optional[WalletType] = None,
        **kwargs,
    ) -> t.List[AuthWallet]:
        return self.logic.AuthWallet.get_by_auth_user_id(
            self.session_factory(),
            auth_user_id,
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
        network: t.Optional[str] = None,
        wallet_type: t.Optional[WalletType] = None,
    ):
        session = self.session_factory()
        with session.begin_nested():
            if existing_wallet := self.logic.AuthWallet.get_by_auth_user_id(
                session,
                auth_user_id,
            ):
                raise RuntimeError("WalletExistsForNetworkAndWalletType")

            return self.logic.AuthWallet.add(
                session,
                public_address,
                encrypted_private_address,
                wallet_type,
                network,
                management_type=wallet_management_type,
                auth_user_id=auth_user_id,
            )
