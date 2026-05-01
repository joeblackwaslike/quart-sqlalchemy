import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.model import SoftDeleteMixin

from ...base import SimpleTestBase

sa = sqlalchemy


class TestSoftDeleteFeature(SimpleTestBase):
    @pytest.fixture
    def Post(self, db: SQLAlchemy, User: type[t.Any]) -> type:
        class Post(SoftDeleteMixin, db.Base):
            __tablename__ = "post"
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
            title: Mapped[str] = sa.orm.mapped_column()
            user_id: Mapped[int | None] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[User | None] = sa.orm.relationship(backref="posts")

        db.create_all()
        return Post

    def test_inactive_filtered(self, db: SQLAlchemy, Post: type[t.Any]):
        with db.bind.Session() as s:
            with s.begin():
                post = Post(title="hello")
                s.add(post)
                s.flush()
                s.refresh(post)

        with db.bind.Session() as s:
            with s.begin():
                post.soft_delete()
                s.add(post)

        with db.bind.Session() as s:
            posts = s.scalars(sa.select(Post)).all()
            assert len(posts) == 0

            posts = s.scalars(sa.select(Post).execution_options(include_soft_deleted=True)).all()
            assert len(posts) == 1
            select_post = posts.pop()

            assert select_post.id == post.id
            assert select_post.deleted_at is not None
