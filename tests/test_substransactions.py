import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
import sqlalchemy
import sqlalchemy.orm
from quart import Quart
from quart.ctx import AppContext
from quart.globals import _cv_app
from quart.globals import app_ctx
from sqlalchemy import Column
from sqlalchemy import event
from sqlalchemy import Integer
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from quart_sqlalchemy import SQLAlchemy


sa = sqlalchemy


@contextmanager
def fake_app_context(app):
    ctx = AppContext(app)
    reset_token = _cv_app.set(ctx)

    try:
        yield ctx
    finally:
        _cv_app.reset(reset_token)


def get_identity_key():
    try:
        task = asyncio.current_task()
        return id(task)
    except RuntimeError:

        try:
            ctx = app_ctx._get_current_object()
            return id(ctx)
        except RuntimeError:

            try:
                from greenlet import getcurrent as ident_func
            except ImportError:
                from threading import get_ident as ident_func

            identity = ident_func()
            if not isinstance(identity, int):
                identity = id(identity)

            return identity


engine_options = dict()
session_options = dict(
    expire_on_commit=False,
    class_=Session,
)

ext_session_options = session_options.copy()
ext_session_options.update(scopefunc=get_identity_key)


app = Quart(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///file:temp.db?mode=memory&cache=shared&uri=true"
app.config["SQLALCHEMY_BINDS"] = {
    "read-replica": "sqlite:///file:temp.db?mode=memory&cache=shared&uri=true",
    "async": "sqlite+aiosqlite:///file:temp.db?mode=memory&cache=shared&uri=true",
}

database = SQLAlchemy(engine_options=engine_options, session_options=ext_session_options)
database.init_app(app)


class Foo(database.Model):
    __tablename__ = "foo"
    id: Mapped[int] = sa.orm.mapped_column(primary_key=True)


class Bar(database.Model):
    __tablename__ = "bar"
    id: Mapped[int] = sa.orm.mapped_column(primary_key=True)


@contextmanager
def nested_namespace(
    db,
    app,
    bind=None,
    engine=None,
    session_options=session_options,
    scopefunc=get_identity_key,
):
    ns = SimpleNamespace()

    # note: you can replace the db._app_engines hack with db.engine if you use `fake_app_context(app)`
    ns.engine = engine or db._app_engines[app][bind]
    with ns.engine.connect() as ns.connection:
        with ns.connection.begin() as ns.transaction:

            ns.Session = scoped_session(
                sessionmaker(
                    bind=ns.connection,
                    query_cls=db.Query,
                    **session_options,
                    join_transaction_mode="create_savepoint",
                ),
                scopefunc=scopefunc,
            )

            ns.nested = ns.connection.begin_nested()

            def end_savepoint(session, transaction):
                if not ns.nested.is_active:
                    ns.nested = ns.connection.begin_nested()

            if not event.contains(ns.Session, "after_transaction_end", end_savepoint):
                event.listen(ns.Session, "after_transaction_end", end_savepoint)

            with ns.Session() as ns.session:
                try:
                    yield ns
                except Exception:
                    ns.session.rollback()
                    raise

            ns.transaction.rollback()

        assert ns.connection.exec_driver_sql("select count(*) from foo").scalar() == 0
        assert ns.connection.exec_driver_sql("select count(*) from bar").scalar() == 0

    ns.Session.remove()


class TestSQLAOnly:
    @pytest.fixture(scope="session")
    def app(self):
        return app

    @pytest.fixture(scope="session")
    def db(self, app):
        database.metadata.create_all(bind=database._app_engines[app][None])
        yield database

    @pytest.fixture
    def db_session(self, app, db, mocker):
        with nested_namespace(db, app, bind=None) as ns:
            mocker.patch.dict(
                db._app_engines[app],
                {key: ns.engine for key in db._app_engines[app]},
            )
            mocker.patch.object(db, "session", new=ns.Session)
            mocker.patch.object(db, "_make_scoped_session", return_value=ns.session)
            yield ns.session

    def test_easy(self, db_session):
        foo = Foo()
        db_session.add(foo)
        db_session.commit()

        foos = db_session.execute(select(Foo)).scalars().all()
        assert len(foos) == 1

    def test_something(self, db_session):
        db_session.add(Foo())
        db_session.commit()

        # core test
        assert db_session.scalar(text("select count(1) from foo")) == 1

        # orm test
        statement = select(Foo)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 1

    def test_something_with_rollbacks(self, db_session):
        # if the SAVEPOINT steps are taken, then a test can also
        # use session.rollback() and continue working with the database

        db_session.add(Foo())
        db_session.commit()

        # core test
        assert db_session.scalar(text("select count(1) from foo")) == 1

        # orm test
        statement = select(Foo)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 1

        db_session.add(Bar())
        db_session.flush()

        # core test
        assert db_session.scalar(text("select count(1) from foo")) == 1
        assert db_session.scalar(text("select count(1) from bar")) == 1

        # orm test
        statement = select(Foo)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 1

        statement = select(Bar)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 1

        db_session.rollback()

        # core test
        # foo stays committed, bar is rolled back. savepoint worked
        assert db_session.scalar(text("select count(1) from foo")) == 1
        assert db_session.scalar(text("select count(1) from bar")) == 0

        # orm test
        statement = select(Foo)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 1

        statement = select(Bar)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 0

        db_session.add(Foo())
        db_session.commit()

        # core test
        assert db_session.scalar(text("select count(1) from foo")) == 2
        assert db_session.scalar(text("select count(1) from bar")) == 0

        # orm test
        statement = select(Foo)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 2

        statement = select(Bar)
        result = db_session.execute(statement).scalars().all()
        assert len(result) == 0


# @contextmanager
# def fake_context_namespace(
#     db,
#     app,
#     bind=None,
#     engine=None,
#     session_options=session_options,
#     scopefunc=get_identity_key,
# ):
#     with fake_app_context(app):
#         ns = SimpleNamespace()

#         ns.engine = db.engine
#         ns.connection = ns.engine.connect()
#         ns.transaction = ns.connection.begin()
#         ns.Session = scoped_session(
#             sessionmaker(
#                 bind=ns.connection,
#                 query_cls=db.Query,
#                 **session_options,
#             ),
#             scopefunc=scopefunc,
#         )
#         ns.nested = ns.connection.begin_nested()

#         def end_savepoint(session, transaction):
#             nonlocal ns

#             if not ns.nested.is_active:
#                 ns.nested = ns.connection.begin_nested()

#         if not event.contains(ns.Session, "after_transaction_end", end_savepoint):
#             event.listen(ns.Session, "after_transaction_end", end_savepoint)

#         ns.session = ns.Session()
#         try:
#             yield ns
#         except Exception:
#             ns.session.rollback()
#             raise
#         finally:
#             ns.session.close()

#         if ns.nested.is_active:
#             ns.nested.rollback()
#         ns.transaction.rollback()

#         assert ns.connection.exec_driver_sql("select count(*) from foo").scalar() == 0
#         assert ns.connection.exec_driver_sql("select count(*) from bar").scalar() == 0

#         ns.connection.close()
#         ns.Session.remove()
