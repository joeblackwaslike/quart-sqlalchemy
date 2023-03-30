import secrets
import typing as t
from datetime import datetime
from enum import Enum
from enum import IntEnum

import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped

from quart_sqlalchemy.model import SoftDeleteMixin
from quart_sqlalchemy.model import TimestampMixin
from quart_sqlalchemy.sim.app import db
from quart_sqlalchemy.sim.util import ObjectID


sa = sqlalchemy


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return str.__str__(self)


class ConnectInteropStatus(StrEnum):
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"


class Provenance(Enum):
    LINK = 1
    OAUTH = 2
    WEBAUTHN = 3
    SMS = 4
    IDENTIFIER = 5
    FEDERATED = 6


class EntityType(Enum):
    FORTMATIC = 1
    MAGIC = 2
    CONNECT = 3


class WalletManagementType(IntEnum):
    UNDELEGATED = 1
    DELEGATED = 2


class WalletType(StrEnum):
    ETH = "ETH"
    HARMONY = "HARMONY"
    ICON = "ICON"
    FLOW = "FLOW"
    TEZOS = "TEZOS"
    ZILLIQA = "ZILLIQA"
    POLKADOT = "POLKADOT"
    SOLANA = "SOLANA"
    AVAX = "AVAX"
    ALGOD = "ALGOD"
    COSMOS = "COSMOS"
    CELO = "CELO"
    BITCOIN = "BITCOIN"
    NEAR = "NEAR"
    HELIUM = "HELIUM"
    CONFLUX = "CONFLUX"
    TERRA = "TERRA"
    TAQUITO = "TAQUITO"
    ED = "ED"
    HEDERA = "HEDERA"


class MagicClient(db.Model, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "magic_client"

    id: Mapped[ObjectID] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
    app_name: Mapped[str] = sa.orm.mapped_column(default="my new app")
    rate_limit_tier: Mapped[t.Optional[str]]
    connect_interop: Mapped[t.Optional[ConnectInteropStatus]]
    is_signing_modal_enabled: Mapped[bool] = sa.orm.mapped_column(default=False)
    global_audience_enabled: Mapped[bool] = sa.orm.mapped_column(default=False)

    public_api_key: Mapped[str] = sa.orm.mapped_column(default_factory=secrets.token_hex)
    secret_api_key: Mapped[str] = sa.orm.mapped_column(default_factory=secrets.token_hex)

    auth_users: Mapped[t.List["AuthUser"]] = sa.orm.relationship(
        back_populates="magic_client",
        primaryjoin="and_(foreign(AuthUser.client_id) == MagicClient.id, AuthUser.user_type != 1)",
    )


class AuthUser(db.Model, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "auth_user"

    id: Mapped[ObjectID] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[t.Optional[str]] = sa.orm.mapped_column(index=True)
    phone_number: Mapped[t.Optional[str]] = sa.orm.mapped_column(index=True)
    user_type: Mapped[int] = sa.orm.mapped_column(default=EntityType.FORTMATIC.value)
    date_verified: Mapped[t.Optional[datetime]]
    provenance: Mapped[t.Optional[Provenance]]
    is_admin: Mapped[bool] = sa.orm.mapped_column(default=False)
    client_id: Mapped[ObjectID]
    linked_primary_auth_user_id: Mapped[t.Optional[ObjectID]]
    global_auth_user_id: Mapped[t.Optional[ObjectID]]

    delegated_user_id: Mapped[t.Optional[str]]
    delegated_identity_pool_id: Mapped[t.Optional[str]]

    current_session_token: Mapped[t.Optional[str]]

    magic_client: Mapped[MagicClient] = sa.orm.relationship(
        back_populates="auth_user",
        uselist=False,
    )
    linked_primary_auth_user = sa.orm.relationship(
        "AuthUser",
        remote_side=[id],
        lazy="joined",
        join_depth=1,
        uselist=False,
    )
    wallets: Mapped[t.List["AuthWallet"]] = sa.orm.relationship(back_populates="auth_user")

    @hybrid_property
    def is_email_verified(self):
        return self.email is not None and self.date_verified is not None

    @hybrid_property
    def is_waiting_on_email_verification(self):
        return self.email is not None and self.date_verified is None

    @hybrid_property
    def is_new_signup(self):
        return self.date_verified is None

    @hybrid_property
    def has_linked_primary_auth_user(self):
        return bool(self.linked_primary_auth_user_id)

    @hybrid_property
    def is_magic_connect_user(self):
        return self.global_auth_user_id is not None and self.user_type == EntityType.CONNECT.value


class AuthWallet(db.Model, SoftDeleteMixin, TimestampMixin):
    __tablename__ = "auth_user"

    id: Mapped[ObjectID] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
    auth_user_id: Mapped[ObjectID] = sa.orm.mapped_column(sa.ForeignKey("auth_user.id"))
    wallet_type: Mapped[str] = sa.orm.mapped_column(default=WalletType.ETH.value)
    management_type: Mapped[int] = sa.orm.mapped_column(
        default=WalletManagementType.UNDELEGATED.value
    )
    public_address: Mapped[t.Optional[str]] = sa.orm.mapped_column(index=True)
    encrypted_private_address: Mapped[t.Optional[str]]
    network: Mapped[str]
    is_exported: Mapped[bool] = sa.orm.mapped_column(default=False)

    auth_user: Mapped[AuthUser] = sa.orm.relationship(
        back_populates="auth_wallets",
        uselist=False,
    )
