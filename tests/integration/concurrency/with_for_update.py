import logging
import threading
import time

import pytest
import sqlalchemy
import sqlalchemy.orm


sa = sqlalchemy

logging.basicConfig(level=logging.DEBUG)
logging.getLogger("sqlalchemy").setLevel(logging.INFO)

log = logging.getLogger(__name__)


class Base(sa.orm.DeclarativeBase):
    pass


class Thing(Base):
    __tablename__ = "things"

    id = sa.Column(sa.Integer, primary_key=True)
    status = sa.Column(sa.String)


@pytest.fixture(scope="module")
def engine():
    engine = sa.create_engine("sqlite:///")
    # engine = sa.create_engine("postgresql+psycopg2://spikes:sesame@localhost/spikes")
    Base.metadata.create_all(engine)

    yield engine

    Base.metadata.drop_all(engine)


@pytest.fixture(scope="module")
def connection(engine):
    with engine.connect() as conn:
        yield conn


@pytest.fixture
def db(connection):
    transaction = connection.begin()
    session = sa.orm.Session(bind=connection)

    # now we can even `.commit()` such session
    yield session

    session.close()
    transaction.rollback()


def test_select_for_update(engine):
    # scoped_db = scoped_session(sessionmaker(bind=connection))
    scoped_db = sa.orm.scoped_session(sa.orm.sessionmaker(bind=engine))
    db = scoped_db()
    db.add(Thing(status="old"))
    db.commit()

    def first(event, sess_factory, status):
        sess = sess_factory()
        # thing = sess.query(Thing).get(1)
        thing = sess.query(Thing).with_for_update().get(1)
        event.set()  # poke second thread
        log.debug("Make him wait for a while")
        time.sleep(0.263)
        thing.status = status
        sess.commit()
        log.debug("Done!")
        # it is always better to explicitly `.remove()` scoped sessions, but
        # in this case it is not necessary because it will be garbage-collected
        # sess_factory.remove()

    def second(event, sess_factory, status):
        event.wait()  # ensure we are called in the right moment
        sess = sess_factory()
        # thing = sess.query(Thing).get(1)
        thing = sess.query(Thing).with_for_update().get(1)
        thing.status = status
        sess.commit()

    event = threading.Event()
    th1 = threading.Thread(target=first, args=(event, scoped_db, "new"))
    th2 = threading.Thread(target=second, args=(event, scoped_db, "brand_new"))

    th1.start()
    th2.start()

    th1.join()
    th2.join()

    # assert db.query(Thing).filter_by(id=1).one().status == 'new'
    t = db.query(Thing).get(1)
    # it is only mandatory to remove session here, seems like it is not
    # garbage-collected becasue it is in `assert` statement (not sure about that)
    scoped_db.remove()

    assert t.status == "brand_new"
