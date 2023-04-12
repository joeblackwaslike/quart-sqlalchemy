from __future__ import annotations

import typing as t

import pytest
import sqlalchemy
import sqlalchemy.orm
from sqlalchemy.orm import Mapped

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.framework import QuartSQLAlchemy
from quart_sqlalchemy.model.mixins import ComparableMixin
from quart_sqlalchemy.model.mixins import RecursiveDictMixin
from quart_sqlalchemy.model.mixins import ReprMixin
from quart_sqlalchemy.model.mixins import SimpleDictMixin
from quart_sqlalchemy.model.mixins import SoftDeleteMixin
from quart_sqlalchemy.model.mixins import TotalOrderMixin

from ... import base


sa = sqlalchemy


class TestSoftDeleteFeature(base.MixinTestBase):
    @pytest.fixture(scope="class")
    def Post(self, db: SQLAlchemy, User: t.Type[t.Any]) -> t.Generator[t.Type[t.Any], None, None]:
        class Post(SoftDeleteMixin, db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional[User]] = sa.orm.relationship(backref="posts")

        db.create_all()
        yield Post

    def test_inactive_filtered(self, db: SQLAlchemy, Post: t.Type[t.Any]):
        with db.bind.Session() as s:
            with s.begin():
                post = Post(title="hello")
                s.add(post)
                s.flush()
                s.refresh(post)

        with db.bind.Session() as s:
            with s.begin():
                post.is_active = False
                s.add(post)

        with db.bind.Session() as s:
            posts = s.scalars(sa.select(Post)).all()
            assert len(posts) == 0

            posts = s.scalars(sa.select(Post).execution_options(include_inactive=True)).all()
            assert len(posts) == 1
            select_post = posts.pop()

            assert select_post.id == post.id
            assert select_post.is_active is False


class TestComparableMixin(base.MixinTestBase):
    extra_mixins = (TotalOrderMixin,)

    def test_orm_models_comparable(self, db: QuartSQLAlchemy, Todo: t.Any):
        assert ComparableMixin in self.default_mixins

        with db.bind.Session() as s:
            with s.begin():
                todos = [Todo() for _ in range(5)]
                s.add_all(todos)

        with db.bind.Session() as s:
            todos = s.scalars(sa.select(Todo).order_by(Todo.id)).all()

            todo1, todo2, *_ = todos
            assert todo1 < todo2


class TestReprMixin(base.MixinTestBase):
    @pytest.fixture(scope="class")
    def Post(self, db: SQLAlchemy, User: t.Type[t.Any]) -> t.Generator[t.Type[t.Any], None, None]:
        class Post(ReprMixin, db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional[User]] = sa.orm.relationship(backref="posts")

        db.create_all()
        yield Post

    def test_mixin_generates_repr(self, db: QuartSQLAlchemy, Post: t.Any):
        with db.bind.Session() as s:
            with s.begin():
                post = Post()
                s.add(post)
                s.flush()
                s.refresh(post)

        assert repr(post) == f"<{type(post).__name__} {post.id}>"


class TestSimpleDictMixin(base.MixinTestBase):
    extra_mixins = (SimpleDictMixin,)

    @pytest.fixture(scope="class")
    def Post(self, db: SQLAlchemy, User: t.Type[t.Any]) -> t.Generator[t.Type[t.Any], None, None]:
        class Post(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional[User]] = sa.orm.relationship(backref="posts")

        db.create_all()
        yield Post

    def test_mixin_converts_model_to_dict(self, db: QuartSQLAlchemy, Post: t.Any, User: t.Any):
        with db.bind.Session() as s:
            with s.begin():
                user = s.scalars(sa.select(User)).first()
                post = Post(user=user)
                s.add(post)
                s.flush()
                s.refresh(post.user)

        with db.bind.Session() as s:
            with s.begin():
                user = s.scalars(sa.select(User).options(sa.orm.selectinload(User.posts))).first()

        data = user.to_dict()

        for field in data:
            assert data[field] == getattr(user, field)


class TestRecursiveMixin(base.MixinTestBase):
    extra_mixins = (RecursiveDictMixin,)

    @pytest.fixture(scope="class")
    def Post(self, db: SQLAlchemy, User: t.Type[t.Any]) -> t.Generator[t.Type[t.Any], None, None]:
        class Post(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            title: Mapped[str] = sa.orm.mapped_column(default="default")
            user_id: Mapped[t.Optional[int]] = sa.orm.mapped_column(sa.ForeignKey("user.id"))

            user: Mapped[t.Optional[User]] = sa.orm.relationship(backref="posts")

        db.create_all()
        yield Post

    def test_mixin_converts_model_to_dict(self, db: QuartSQLAlchemy, Post: t.Any, User: t.Any):
        with db.bind.Session() as s:
            with s.begin():
                user = s.scalars(sa.select(User)).first()
                post = Post(user=user)
                s.add(post)
                s.flush()
                s.refresh(post.user)

        with db.bind.Session() as s:
            with s.begin():
                user = s.scalars(sa.select(User).options(sa.orm.selectinload(User.posts))).first()

        data = user.to_dict()

        for col in sa.inspect(user).mapper.columns:
            assert data[col.name] == getattr(user, col.name)
