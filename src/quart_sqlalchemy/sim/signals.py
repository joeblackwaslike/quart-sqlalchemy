from blinker import Namespace


# Synchronous signals
_sync = Namespace()

auth_user_duplicate = _sync.signal(
    "auth_user_duplicate",
    doc="""Called on discovery of at least one duplicate auth user.

    Handlers should have the following signature:
        def handler(
            current_app: Quart,
            original_auth_user_id: ObjectID,
            duplicate_auth_user_ids: List[ObjectID],
            session: sa.orm.Session,
        ) -> None:
            ...
    """,
)

keys_rolled = _sync.signal(
    "keys_rolled",
    doc="""Called after api keys are rolled.

    Handlers should have the following signature:
        def handler(
            app: Quart,
            deactivated_keys: Dict[str, Any],
            redis_client: Redis,
            ) -> None:
            ...
    """,
)
