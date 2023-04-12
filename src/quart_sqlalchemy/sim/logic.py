import inspect
import logging
import secrets
import typing as t
from datetime import datetime

import sqlalchemy
import sqlalchemy.orm
from quart import current_app

from quart_sqlalchemy.session import provide_global_contextual_session
from quart_sqlalchemy.sim import signals
from quart_sqlalchemy.sim.model import AuthUser as auth_user_model
from quart_sqlalchemy.sim.model import AuthWallet as auth_wallet_model
from quart_sqlalchemy.sim.model import ConnectInteropStatus
from quart_sqlalchemy.sim.model import EntityType
from quart_sqlalchemy.sim.model import MagicClient as magic_client_model
from quart_sqlalchemy.sim.model import Provenance
from quart_sqlalchemy.sim.model import WalletType
from quart_sqlalchemy.sim.repo_adapter import RepositoryLegacyAdapter
from quart_sqlalchemy.sim.util import ObjectID
from quart_sqlalchemy.sim.util import one
from quart_sqlalchemy.types import EntityIdT
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import SessionT


logger = logging.getLogger(__name__)
sa = sqlalchemy


class LogicMeta(type):
    _ignore = {"LegacyLogicComponent"}

    def __init__(cls, name, bases, cls_dict):
        if not hasattr(cls, "_registry"):
            cls._registry = {}
        else:
            if cls.__name__ not in cls._ignore:
                model = getattr(cls, "model", None)
                if model is not None:
                    name = model.__name__

                cls._registry[name] = cls()

        super().__init__(name, bases, cls_dict)


class LogicComponent(t.Generic[EntityT, EntityIdT, SessionT], metaclass=LogicMeta):
    def __dir__(self):
        return super().__dir__() + list(self._registry.keys())

    def __getattr__(self, name):
        if name in self._registry:
            return self._registry[name]
        else:
            raise AttributeError(f"{type(self).__name__} has no attribute '{name}'")


class MagicClient(LogicComponent[magic_client_model, ObjectID, sa.orm.Session]):
    model = magic_client_model
    identity = ObjectID
    _repository = RepositoryLegacyAdapter(model, identity)

    @provide_global_contextual_session
    def add(self, session, app_name=None, **kwargs):
        public_api_key = secrets.token_hex(16)
        return self._repository.add(
            session,
            app_name=app_name,
            **kwargs,
            public_api_key=public_api_key,
        )

    @provide_global_contextual_session
    def get_by_id(
        self,
        session,
        model_id,
        allow_inactive=False,
        join_list=None,
    ) -> t.Optional[magic_client_model]:
        return self._repository.get_by_id(
            session,
            model_id,
            allow_inactive=allow_inactive,
            join_list=join_list,
        )

    @provide_global_contextual_session
    def get_by_public_api_key(
        self,
        session,
        public_api_key,
    ):
        return one(
            self._repository.get_by(
                session,
                filters=[magic_client_model.public_api_key == public_api_key],
                limit=1,
            )
        )

    @provide_global_contextual_session
    def update_by_id(self, session, model_id, **update_params):
        modified_row = self._repository.update(session, model_id, **update_params)
        session.refresh(modified_row)
        return modified_row

    @provide_global_contextual_session
    def yield_all_clients_by_chunk(self, session, chunk_size):
        yield from self._repository.yield_by_chunk(session, chunk_size)

    @provide_global_contextual_session
    def yield_by_chunk(self, session, chunk_size, filters=None, join_list=None):
        yield from self._repository.yield_by_chunk(
            session,
            chunk_size,
            filters=filters,
            join_list=join_list,
        )


class DuplicateAuthUser(Exception):
    pass


class AuthUserDoesNotExist(Exception):
    pass


class MissingEmail(Exception):
    pass


class MissingPhoneNumber(Exception):
    pass


class AuthUser(LogicComponent[auth_user_model, ObjectID, sa.orm.Session]):
    model = auth_user_model
    identity = ObjectID
    _repository = RepositoryLegacyAdapter(model, identity)

    @provide_global_contextual_session
    def add(self, session, **kwargs) -> auth_user_model:
        return self._repository.add(session, **kwargs)

    @provide_global_contextual_session
    def add_by_email_and_client_id(
        self,
        session,
        client_id,
        email=None,
        user_type=EntityType.FORTMATIC.value,
        **kwargs,
    ):
        if email is None:
            raise MissingEmail()

        if self.exist_by_email_and_client_id(
            session,
            email,
            client_id,
            user_type=user_type,
        ):
            logger.exception(
                "User duplication for email: {} (client_id: {})".format(
                    email,
                    client_id,
                ),
            )
            raise DuplicateAuthUser()

        row = self._repository.add(
            session,
            email=email,
            client_id=client_id,
            user_type=user_type,
            **kwargs,
        )
        logger.info(
            "New auth user (id: {}) created by email (client_id: {})".format(
                row.id,
                client_id,
            ),
        )

        return row

    @provide_global_contextual_session
    def add_by_client_id(
        self,
        session,
        client_id,
        user_type=EntityType.FORTMATIC.value,
        provenance=None,
        global_auth_user_id=None,
        is_verified=False,
    ):
        row = self._repository.add(
            session,
            client_id=client_id,
            user_type=user_type,
            provenance=provenance,
            global_auth_user_id=global_auth_user_id,
            date_verified=datetime.utcnow() if is_verified else None,
        )
        logger.info(
            "New auth user (id: {}) created by (client_id: {})".format(row.id, client_id),
        )

        return row

    @provide_global_contextual_session
    def get_by_session_token(
        self,
        session,
        session_token,
    ):
        return one(
            self._repository.get_by(
                session,
                filters=[auth_user_model.current_session_token == session_token],
                limit=1,
            )
        )

    @provide_global_contextual_session
    def get_by_active_identifier_and_client_id(
        self,
        session,
        identifier_field,
        identifier_value,
        client_id,
        user_type,
        for_update=False,
    ) -> t.Optional[auth_user_model]:
        """There should only be one active identifier where all the parameters match for a given client ID. In the case of multiple results, the subsequent entries / "dupes" will be marked as inactive."""
        filters = [
            identifier_field == identifier_value,
            auth_user_model.client_id == client_id,
            auth_user_model.user_type == user_type,
        ]

        results = self._repository.get_by(
            session,
            filters=filters,
            order_by_clause=auth_user_model.id.asc(),
            for_update=for_update,
        )

        if not results:
            return None

        original, *duplicates = results

        if duplicates:
            signals.auth_user_duplicate.send(
                current_app,
                original_auth_user_id=original.id,
                duplicate_auth_user_ids=[dupe.id for dupe in duplicates],
            )

        return original

    @provide_global_contextual_session
    def get_by_email_and_client_id(
        self,
        session,
        email,
        client_id,
        user_type=EntityType.FORTMATIC.value,
        for_update=False,
    ):
        return self.get_by_active_identifier_and_client_id(
            session=session,
            identifier_field=auth_user_model.email,
            identifier_value=email,
            client_id=client_id,
            user_type=user_type,
            for_update=for_update,
        )

    @provide_global_contextual_session
    def exist_by_email_and_client_id(
        self,
        session,
        email,
        client_id,
        user_type=EntityType.FORTMATIC.value,
    ):
        return bool(
            self._repository.exist(
                session,
                filters=[
                    auth_user_model.email == email,
                    auth_user_model.client_id == client_id,
                    auth_user_model.user_type == user_type,
                ],
            ),
        )

    @provide_global_contextual_session
    def get_by_id(
        self, session, model_id, join_list=None, for_update=False
    ) -> t.Optional[auth_user_model]:
        return self._repository.get_by_id(
            session,
            model_id,
            join_list=join_list,
            for_update=for_update,
        )

    @provide_global_contextual_session
    def update_by_id(self, session, auth_user_id, **kwargs):
        modified_user = self._repository.update(session, auth_user_id, **kwargs)

        if modified_user is None:
            raise AuthUserDoesNotExist()

        return modified_user

    @provide_global_contextual_session
    def get_user_count_by_client_id_and_user_type(self, session, client_id, user_type):
        query = (
            session.query(auth_user_model)
            .filter(
                auth_user_model.client_id == client_id,
                auth_user_model.user_type == user_type,
                auth_user_model.date_verified.is_not(None),
            )
            .statement.with_only_columns(sa.func.count())
            .order_by(None)
        )

        return session.execute(query).scalar()

    @provide_global_contextual_session
    def get_by_client_id_and_user_type(
        self,
        session,
        client_id,
        user_type,
        offset=None,
        limit=None,
    ):
        return self.get_by_client_ids_and_user_type(
            session,
            [client_id],
            user_type,
            offset=offset,
            limit=limit,
        )

    @provide_global_contextual_session
    def yield_by_chunk(self, session, chunk_size, filters=None, join_list=None):
        yield from self._repository.yield_by_chunk(
            session,
            chunk_size,
            filters=filters,
            join_list=join_list,
        )

    @provide_global_contextual_session
    def get_by_emails_and_client_id(
        self,
        session,
        email_ids,
        client_id,
    ):
        return self._repository.get_by(
            session,
            filters=[
                auth_user_model.email.in_(email_ids),
                auth_user_model.client_id == client_id,
            ],
        )

    @provide_global_contextual_session
    def get_by_email(
        self,
        session,
        email: str,
        join_list=None,
        filters=None,
        for_update: bool = False,
    ) -> t.List[auth_user_model]:
        filters = filters or []
        combined_filters = filters + [auth_user_model.email == email]

        return self._repository.get_by(
            session,
            filters=combined_filters,
            for_update=for_update,
            join_list=join_list,
        )


class AuthWallet(LogicComponent[auth_wallet_model, ObjectID, sa.orm.Session]):
    model = auth_wallet_model
    identity = ObjectID
    _repository = RepositoryLegacyAdapter(model, identity)

    @provide_global_contextual_session
    def add(
        self,
        session,
        public_address,
        encrypted_private_address,
        wallet_type,
        network,
        management_type=None,
        auth_user_id=None,
    ):
        new_row = self._repository.add(
            session,
            auth_user_id=auth_user_id,
            public_address=public_address,
            encrypted_private_address=encrypted_private_address,
            wallet_type=wallet_type,
            management_type=management_type,
            network=network,
        )

        return new_row

    @provide_global_contextual_session
    def get_by_id(self, session, model_id, allow_inactive=False, join_list=None):
        return self._repository.get_by_id(
            session,
            model_id,
            allow_inactive=allow_inactive,
            join_list=join_list,
        )

    @provide_global_contextual_session
    def get_by_public_address(self, session, public_address, network=None, is_active=True):
        filters = [
            auth_wallet_model.public_address == public_address,
        ]

        if network:
            filters.append(auth_wallet_model.network == network)

        row = self._repository.get_by(session, filters=filters, allow_inactive=not is_active)

        if not row:
            return None

        return one(row)

    @provide_global_contextual_session
    def get_by_auth_user_id(
        self,
        session,
        auth_user_id,
        network=None,
        wallet_type=None,
        is_active=True,
        join_list=None,
    ):
        filters = [
            auth_wallet_model.auth_user_id == auth_user_id,
        ]

        if network:
            filters.append(auth_wallet_model.network == network)

        if wallet_type:
            filters.append(auth_wallet_model.wallet_type == wallet_type)

        rows = self._repository.get_by(
            session, filters=filters, join_list=join_list, allow_inactive=not is_active
        )

        if not rows:
            return []

        return rows

    @provide_global_contextual_session
    def update_by_id(self, session, model_id, **kwargs):
        self._repository.update(session, model_id, **kwargs)
