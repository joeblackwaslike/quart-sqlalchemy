import logging
import typing as t
from datetime import datetime
from functools import wraps

from sqlalchemy import or_
from sqlalchemy.orm import contains_eager
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

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


logger = logging.getLogger(__name__)


class LogicMeta(type):
    """This is metaclass provides registry pattern where all the available
    logics will be accessible through any instantiated logic object.

    Note:
        Don't use this metaclass at another places. This is only intended to be
        used by LogicComponent. If you want your own registry, please create
        your own.
    """

    def __init__(cls, name, bases, cls_dict):
        if not hasattr(cls, "_registry"):
            cls._registry = {}
        else:
            cls._registry[name] = cls()

        super().__init__(name, bases, cls_dict)


class LogicComponent(metaclass=LogicMeta):
    """This is the base class for any logic class. This overrides the getattr
    method for registry lookup.

    Example:

        ```
        class TrollGoat(LogicComponent):

            def add(x):
                print(x)
        ```

        Once you have a logic object, you can directly do something like:

            ```
            logic.TrollGoat.add('troll_goat')
            ```

    Note:
        You will have to explicitly import your newly created logic in
        ``fortmatic.logic.__init__.py``. When the logic is imported, it is created
        the first time; hence, it is then registered. If this is unclear to you,
        read https://blog.ionelmc.ro/2015/02/09/understanding-python-metaclasses/
        It has all the info you need to understand. For example, everything in
        python is an object :P. Enjoy.
    """

    def __dir__(self):
        return super().__dir__() + list(self._registry.keys())

    def __getattr__(self, logic_name):
        if logic_name in self._registry:
            return self._registry[logic_name]
        else:
            raise AttributeError(
                "{object_name} has no attribute '{logic_name}'".format(
                    object_name=self.__class__.__name__,
                    logic_name=logic_name,
                ),
            )


class MagicClient(LogicComponent):
    def __init__(self):
        # self._repository = SQLAlchemyRepository[magic_client_model, ObjectID](session)

        self._repository = RepositoryLegacyAdapter(magic_client_model, ObjectID)

    def _add(self, session, app_name=None):
        return self._repository.add(
            session,
            app_name=app_name,
        )

    # add = with_db_session(ro=False)(_add)
    add = _add

    # @with_db_session(ro=True)
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

    # @with_db_session(ro=True)
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

    # @with_db_session(ro=True)
    # def get_magic_api_user_id_by_client_id(self, session, magic_client_id):
    #     client = self._repository.get_by_id(
    #         session,
    #         magic_client_id,
    #         allow_inactive=False,
    #         join_list=None,
    #     )

    #     if client is None:
    #         return None

    #     if client.magic_client_api_user is None:
    #         return None

    #     return client.magic_client_api_user.magic_api_user_id

    # @with_db_session(ro=False)
    def update_by_id(self, session, model_id, **update_params):
        modified_row = self._repository.update(session, model_id, **update_params)
        session.refresh(modified_row)
        return modified_row

    # @with_db_session(ro=True)
    def yield_all_clients_by_chunk(self, session, chunk_size):
        yield from self._repository.yield_by_chunk(session, chunk_size)

    # @with_db_session(ro=True)
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


class AuthUser(LogicComponent):
    def __init__(self):
        # self._repository = SQLRepository(auth_user_model)
        self._repository = RepositoryLegacyAdapter(magic_client_model, ObjectID)

    # @with_db_session(ro=True)
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

    def _get_or_add_by_phone_number_and_client_id(
        self,
        session,
        client_id,
        phone_number,
        user_type=EntityType.FORTMATIC.value,
    ):
        if phone_number is None:
            raise MissingPhoneNumber()

        row = self._get_by_phone_number_and_client_id(
            session=session,
            phone_number=phone_number,
            client_id=client_id,
            user_type=user_type,
        )

        if row:
            return row

        row = self._repository.add(
            session=session,
            phone_number=phone_number,
            client_id=client_id,
            user_type=user_type,
            provenance=Provenance.SMS,
        )
        logger.info(
            "New auth user (id: {}) created by phone number (client_id: {})".format(
                row.id,
                client_id,
            ),
        )

        return row

    # get_or_add_by_phone_number_and_client_id = with_db_session(ro=False)(
    #     _get_or_add_by_phone_number_and_client_id,
    # )
    get_or_add_by_phone_number_and_client_id = _get_or_add_by_phone_number_and_client_id

    def _add_by_email_and_client_id(
        self,
        session,
        client_id,
        email=None,
        user_type=EntityType.FORTMATIC.value,
        **kwargs,
    ):
        if email is None:
            raise MissingEmail()

        if self._exist_by_email_and_client_id(
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

    # add_by_email_and_client_id = with_db_session(ro=False)(_add_by_email_and_client_id)
    add_by_email_and_client_id = _add_by_email_and_client_id

    def _add_by_client_id(
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
            "New auth user (id: {}) created by (client_id: {})".format(
                row.id,
                client_id,
            ),
        )

        return row

    # add_by_client_id = with_db_session(ro=False)(_add_by_client_id)
    add_by_client_id = _add_by_client_id

    def _get_by_active_identifier_and_client_id(
        self,
        session,
        identifier_field,
        identifier_value,
        client_id,
        user_type,
    ) -> auth_user_model:
        """There should only be one active identifier where all the parameters match for a given client ID. In the case of multiple results, the subsequent entries / "dupes" will be marked as inactive."""
        filters = [
            identifier_field == identifier_value,
            auth_user_model.client_id == client_id,
            auth_user_model.user_type == user_type,
            # auth_user_model.is_active == True,  # noqa: E712
        ]

        results = self._repository.get_by(
            session,
            filters=filters,
            order_by_clause=auth_user_model.id.asc(),
        )

        if not results:
            return None

        original, *duplicates = results

        if duplicates:
            signals.auth_user_duplicate.send(
                original_auth_user_id=original.id,
                duplicate_auth_user_ids=[dupe.id for dupe in duplicates],
            )

        return original

    # @with_db_session(ro=True)
    def get_by_email_and_client_id(
        self,
        session,
        email,
        client_id,
        user_type=EntityType.FORTMATIC.value,
    ):
        return self._get_by_active_identifier_and_client_id(
            session=session,
            identifier_field=auth_user_model.email,
            identifier_value=email,
            client_id=client_id,
            user_type=user_type,
        )

    def _get_by_phone_number_and_client_id(
        self,
        session,
        phone_number,
        client_id,
        user_type=EntityType.FORTMATIC.value,
    ):
        if phone_number is None:
            raise MissingPhoneNumber()

        return self._get_by_active_identifier_and_client_id(
            session=session,
            identifier_field=auth_user_model.phone_number,
            identifier_value=phone_number,
            client_id=client_id,
            user_type=user_type,
        )

    # get_by_phone_number_and_client_id = with_db_session(ro=True)(
    #     _get_by_phone_number_and_client_id,
    # )
    get_by_phone_number_and_client_id = _get_by_phone_number_and_client_id

    def _exist_by_email_and_client_id(
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

    # exist_by_email_and_client_id = with_db_session(ro=True)(_exist_by_email_and_client_id)
    exist_by_email_and_client_id = _exist_by_email_and_client_id

    def _get_by_id(self, session, model_id, join_list=None, for_update=False) -> auth_user_model:
        return self._repository.get_by_id(
            session,
            model_id,
            join_list=join_list,
            for_update=for_update,
        )

    get_by_id = _get_by_id
    # get_by_id = with_db_session(ro=True)(_get_by_id)

    def _update_by_id(self, session, auth_user_id, **kwargs):
        modified_user = self._repository.update(session, auth_user_id, **kwargs)

        if modified_user is None:
            raise AuthUserDoesNotExist()

        return modified_user

    # update_by_id = with_db_session(ro=False)(_update_by_id)
    update_by_id = _update_by_id

    # @with_db_session(ro=True)
    def get_user_count_by_client_id_and_user_type(self, session, client_id, user_type):
        query = (
            session.query(auth_user_model)
            .filter(
                auth_user_model.client_id == client_id,
                auth_user_model.user_type == user_type,
                # auth_user_model.is_active == True,  # noqa: E712
                auth_user_model.date_verified.is_not(None),
            )
            .statement.with_only_columns([func.count()])
            .order_by(None)
        )

        return session.execute(query).scalar()

    def _get_by_client_id_and_global_auth_user(self, session, client_id, global_auth_user_id):
        return self._repository.get_by(
            session=session,
            filters=[
                auth_user_model.client_id == client_id,
                auth_user_model.user_type == EntityType.CONNECT.value,
                # auth_user_model.is_active == True,  # noqa: E712
                auth_user_model.global_auth_user_id == global_auth_user_id,
            ],
        )

    # get_by_client_id_and_global_auth_user = with_db_session(ro=True)(
    #     _get_by_client_id_and_global_auth_user,
    # )
    get_by_client_id_and_global_auth_user = _get_by_client_id_and_global_auth_user

    # @with_db_session(ro=True)
    # def get_by_client_id_for_connect(
    #     self,
    #     session,
    #     client_id,
    #     offset=None,
    #     limit=None,
    # ):
    #     # TODO(thomas|2022-07-12): Determine where/if is the right place to split
    #     # connect/magic logic based on user type as part of https://app.shortcut.com/magic-labs/story/53323.
    #     # See https://github.com/fortmatic/fortmatic/pull/6173#discussion_r919529540.
    #     return (
    #         session.query(auth_user_model)
    #         .join(
    #             identifier_model,
    #             auth_user_model.global_auth_user_id == identifier_model.global_auth_user_id,
    #         )
    #         .filter(
    #             auth_user_model.client_id == client_id,
    #             auth_user_model.user_type == EntityType.CONNECT.value,
    #             auth_user_model.is_active == True,  # noqa: E712,
    #             auth_user_model.provenance == Provenance.IDENTIFIER,
    #             or_(
    #                 identifier_model.identifier_type.in_(
    #                     GlobalAuthUserIdentifierType.get_public_address_enums(),
    #                 ),
    #                 identifier_model.date_verified != None,
    #             ),
    #         )
    #         .order_by(auth_user_model.id.desc())
    #         .limit(limit)
    #         .offset(offset)
    #     ).all()

    # @with_db_session(ro=True)
    # def get_user_count_by_client_id_for_connect(
    #     self,
    #     session,
    #     client_id,
    # ):
    #     # TODO(thomas|2022-07-12): Determine where/if is the right place to split
    #     # connect/magic logic based on user type as part of https://app.shortcut.com/magic-labs/story/53323.
    #     # See https://github.com/fortmatic/fortmatic/pull/6173#discussion_r919529540.
    #     query = (
    #         session.query(auth_user_model)
    #         .join(
    #             identifier_model,
    #             auth_user_model.global_auth_user_id == identifier_model.global_auth_user_id,
    #         )
    #         .filter(
    #             auth_user_model.client_id == client_id,
    #             auth_user_model.user_type == EntityType.CONNECT.value,
    #             auth_user_model.is_active == True,  # noqa: E712,
    #             auth_user_model.provenance == Provenance.IDENTIFIER,
    #             or_(
    #                 identifier_model.identifier_type.in_(
    #                     GlobalAuthUserIdentifierType.get_public_address_enums(),
    #                 ),
    #                 identifier_model.date_verified != None,
    #             ),
    #         )
    #         .statement.with_only_columns(
    #             [func.count(distinct(auth_user_model.global_auth_user_id))],
    #         )
    #         .order_by(None)
    #     )

    #     return session.execute(query).scalar()

    # @with_db_session(ro=True)
    def get_by_client_id_and_user_type(
        self,
        session,
        client_id,
        user_type,
        offset=None,
        limit=None,
    ):
        return self._get_by_client_ids_and_user_type(
            session,
            [client_id],
            user_type,
            offset=offset,
            limit=limit,
        )

    def _get_by_client_ids_and_user_type(
        self,
        session,
        client_ids,
        user_type,
        offset=None,
        limit=None,
    ):
        if not client_ids:
            return []

        return self._repository.get_by(
            session,
            filters=[
                auth_user_model.client_id.in_(client_ids),
                auth_user_model.user_type == user_type,
                # auth_user_model.is_active == True,  # noqa: E712,
                auth_user_model.date_verified != None,
            ],
            offset=offset,
            limit=limit,
            order_by_clause=auth_user_model.id.desc(),
        )

    # get_by_client_ids_and_user_type = with_db_session(ro=True)(
    #     _get_by_client_ids_and_user_type,
    # )
    get_by_client_ids_and_user_type = _get_by_client_ids_and_user_type

    def _get_by_client_id_with_substring_search(
        self,
        session,
        client_id,
        substring,
        offset=None,
        limit=10,
        join_list=None,
    ):
        return self._repository.get_by(
            session,
            filters=[
                auth_user_model.client_id == client_id,
                auth_user_model.user_type == EntityType.MAGIC.value,
                or_(
                    auth_user_model.provenance == Provenance.SMS,
                    auth_user_model.provenance == Provenance.LINK,
                    auth_user_model.provenance == None,  # noqa: E711
                ),
                or_(
                    auth_user_model.phone_number.contains(substring),
                    auth_user_model.email.contains(substring),
                ),
            ],
            offset=offset,
            limit=limit,
            order_by_clause=auth_user_model.id.desc(),
            join_list=join_list,
        )

    # get_by_client_id_with_substring_search = with_db_session(ro=True)(
    #     _get_by_client_id_with_substring_search,
    # )
    get_by_client_id_with_substring_search = _get_by_client_id_with_substring_search

    # @with_db_session(ro=True)
    def yield_by_chunk(self, session, chunk_size, filters=None, join_list=None):
        yield from self._repository.yield_by_chunk(
            session,
            chunk_size,
            filters=filters,
            join_list=join_list,
        )

    # @with_db_session(ro=True)
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

    def _get_by_email(
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

    # get_by_email = with_db_session(ro=True)(_get_by_email)
    get_by_email = _get_by_email

    def _add(self, session, **kwargs) -> ObjectID:
        return self._repository.add(session, **kwargs).id

    # add = with_db_session(ro=False)(_add)
    add = _add

    def _get_by_email_for_interop(
        self,
        session,
        email: str,
        wallet_type: WalletType,
        network: str,
    ) -> t.List[auth_user_model]:
        """
        Custom method for searching for users eligible for interop. Unfortunately, this can't be done with the current
        abstractions in our sql_repository, so this is a one-off bespoke method.
        If we need to add more similar queries involving eager loading and multiple joins, we can add an abstraction
        inside the repository.
        """

        query = (
            session.query(auth_user_model)
            .join(
                auth_user_model.wallets.and_(
                    auth_wallet_model.wallet_type == str(wallet_type)
                ).and_(auth_wallet_model.network == network)
                # .and_(auth_wallet_model.is_active == 1),
            )
            .options(contains_eager(auth_user_model.wallets))
            .join(
                auth_user_model.magic_client.and_(
                    magic_client_model.connect_interop == ConnectInteropStatus.ENABLED,
                ),
            )
            .options(contains_eager(auth_user_model.magic_client))
            # TODO(magic-ravi#67899|2022-12-30): Uncomment to allow account-linked users to use interop
            # .options(
            #     joinedload(
            #         auth_user_model.linked_primary_auth_user,
            #     ).joinedload("auth_wallets"),
            # )
            .filter(
                auth_wallet_model.wallet_type == wallet_type,
                auth_wallet_model.network == network,
            )
            .filter(
                auth_user_model.email == email,
                auth_user_model.user_type == EntityType.MAGIC.value,
                # auth_user_model.is_active == 1,
                auth_user_model.linked_primary_auth_user_id == None,  # noqa: E711
            )
            .populate_existing()
        )

        return query.all()

    # get_by_email_for_interop = with_db_session(ro=True)(
    #     _get_by_email_for_interop,
    # )
    get_by_email_for_interop = _get_by_email_for_interop

    def _get_linked_users(self, session, primary_auth_user_id, join_list, no_op=False):
        # TODO(magic-ravi#67899|2022-12-30): Re-enable account linked users for interop. Remove no_op flag.
        if no_op:
            return []
        else:
            return self._repository.get_by(
                session,
                filters=[
                    # auth_user_model.is_active == True,  # noqa: E712
                    auth_user_model.user_type == EntityType.MAGIC.value,
                    auth_user_model.linked_primary_auth_user_id == primary_auth_user_id,
                ],
                join_list=join_list,
            )

    # get_linked_users = with_db_session(ro=True)(_get_linked_users)
    get_linked_users = _get_linked_users

    # @with_db_session(ro=True)
    def get_by_phone_number(self, session, phone_number):
        return self._repository.get_by(
            session,
            filters=[
                auth_user_model.phone_number == phone_number,
            ],
        )


class AuthWallet(LogicComponent):
    def __init__(self):
        # self._repository = SQLAlchemyRepository[magic_client_model, ObjectID](session)
        self._repository = RepositoryLegacyAdapter(auth_wallet_model, ObjectID)

    def _add(
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

    # add = with_db_session(ro=False)(_add)
    add = _add

    # @with_db_session(ro=True)
    def get_by_id(self, session, model_id, allow_inactive=False, join_list=None):
        return self._repository.get_by_id(
            session,
            model_id,
            allow_inactive=allow_inactive,
            join_list=join_list,
        )

    # @with_db_session(ro=True)
    def get_by_public_address(self, session, public_address, network=None, is_active=True):
        """Public address is unique in our system. In any case, we should only
        find one row for the given public address.

        Args:
            session: A database session object.
            public_address (str): A public address.
            network (str): A network name.
            is_active (boolean): A boolean value to denote if the query should
                retrieve active or inactive rows.

        Returns:
            A formatted row, either in presenter form or raw db row.
        """
        filters = [
            auth_wallet_model.public_address == public_address,
            # auth_wallet_model.is_active == is_active,
        ]

        if network:
            filters.append(auth_wallet_model.network == network)

        row = self._repository.get_by(session, filters=filters, allow_inactive=not is_active)

        if not row:
            return None

        return one(row)

    # @with_db_session(ro=True)
    def get_by_auth_user_id(
        self,
        session,
        auth_user_id,
        network=None,
        wallet_type=None,
        is_active=True,
        join_list=None,
    ):
        """Return all the associated wallets for the given user id.

        Args:
            session: A database session object.
            auth_user_id (ObjectID): A auth_user id.
            network (str|None): A network name.
            wallet_type (str|None): a wallet type like ETH or BTC
            is_active (boolean): A boolean value to denote if the query should
                retrieve active or inactive rows.
            join_list (None|List): Table you wish to join.

        Returns:
            An empty list or a list of wallets.
        """
        filters = [
            auth_wallet_model.auth_user_id == auth_user_id,
            # auth_wallet_model.is_active == is_active,
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

    def _update_by_id(self, session, model_id, **kwargs):
        self._repository.update(session, model_id, **kwargs)

    # update_by_id = with_db_session(ro=False)(_update_by_id)
    update_by_id = _update_by_id
