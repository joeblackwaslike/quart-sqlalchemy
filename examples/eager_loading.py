from __future__ import annotations

from datetime import datetime

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql.selectable
from sqlalchemy.orm import Mapped, mapped_column

sa = sqlalchemy

engine = sa.create_engine("sqlite://", echo=False)
Base = sa.orm.declarative_base()
Session = sa.orm.sessionmaker(bind=engine, expire_on_commit=False)


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(sa.Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=True)
    time_created: Mapped[datetime] = mapped_column(
        default=sa.func.now(),
        server_default=sa.FetchedValue(),
    )
    time_updated: Mapped[datetime] = mapped_column(
        default=sa.func.now(),
        onupdate=sa.func.now(),
        server_default=sa.FetchedValue(),
        server_onupdate=sa.FetchedValue(),
    )

    posts = sa.orm.relationship("Post", back_populates="user")


class Post(Base):
    __tablename__ = "post"

    id: Mapped[int] = mapped_column(sa.Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(sa.ForeignKey("user.id"), nullable=True)

    user = sa.orm.relationship("User", back_populates="posts", uselist=False)


Base.metadata.create_all(bind=engine)

with Session() as session:
    with session.begin():
        user = User(name="joe", posts=[Post(), Post()])
        session.add(user)
        session.flush()
        session.refresh(user)


with Session() as session:
    statement = sa.select(User).where(User.id == user.id)
    eager_statement = statement.options(sa.orm.joinedload(User.posts))

print(user.id, user.time_created, user.time_updated)

with Session() as session:
    with session.begin():
        user = session.get(User, user.id)
        new_user = session.merge(User(id=user.id, name="new"))
        session.flush()
        session.refresh(new_user)

# time_updated not fetched, needs to be refreshed
# print(new_user.name, new_user.time_created)

print(user.id, user.name, user.time_created, user.time_updated)

with Session() as session:
    user = session.get(User, new_user.id)

print(user.id, user.name, user.time_created, user.time_updated)

>>> print(user.id, user.time_created, user.time_updated)
'1 2023-03-21 18:02:56 2023-03-21 18:02:56'