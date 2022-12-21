from __future__ import annotations

import typing as t
from typing import Optional

import pytest
from quart import Quart
from werkzeug.exceptions import NotFound

from quart_sqlalchemy import SQLAlchemy
from quart_sqlalchemy.pagination import Pagination


class RangePagination(Pagination):
    def __init__(
        self, total: Optional[int] = 150, page: int = 1, per_page: int = 10
    ) -> None:
        if total is None:
            self._data = range(150)
        else:
            self._data = range(total)

        super().__init__(total=total, page=page, per_page=per_page)

        if total is None:
            self.total = None

    def _query_items(self) -> list[t.Any]:
        first = self._query_offset
        last = first + self.per_page + 1
        return list(self._data[first:last])

    def _query_count(self) -> int:
        return len(self._data)


def test_first_page() -> None:
    p = RangePagination()
    assert p.page == 1
    assert p.per_page == 10
    assert p.total == 150
    assert p.pages == 15
    assert not p.has_prev
    assert p.prev_num is None
    assert p.has_next
    assert p.next_num == 2


def test_last_page() -> None:
    p = RangePagination(page=15)
    assert p.page == 15
    assert p.has_prev
    assert p.prev_num == 14
    assert not p.has_next
    assert p.next_num is None


def test_item_numbers_first_page() -> None:
    p = RangePagination()
    p.items = list(range(10))
    assert p.first == 1
    assert p.last == 10


def test_item_numbers_last_page() -> None:
    p = RangePagination(page=15)
    p.items = list(range(5))
    assert p.first == 141
    assert p.last == 145


def test_item_numbers_0() -> None:
    p = RangePagination(total=0)
    assert p.first == 0
    assert p.last == 0


@pytest.mark.parametrize("total", [0, None])
def test_0_pages(total: int | None) -> None:
    p = RangePagination(total=total)
    assert p.pages == 0
    assert not p.has_prev
    assert not p.has_next


@pytest.mark.parametrize(
    ("page", "expect"),
    [
        (1, [1, 2, 3, 4, 5, None, 14, 15]),
        (2, [1, 2, 3, 4, 5, 6, None, 14, 15]),
        (3, [1, 2, 3, 4, 5, 6, 7, None, 14, 15]),
        (4, [1, 2, 3, 4, 5, 6, 7, 8, None, 14, 15]),
        (5, [1, 2, 3, 4, 5, 6, 7, 8, 9, None, 14, 15]),
        (6, [1, 2, None, 4, 5, 6, 7, 8, 9, 10, None, 14, 15]),
        (7, [1, 2, None, 5, 6, 7, 8, 9, 10, 11, None, 14, 15]),
        (8, [1, 2, None, 6, 7, 8, 9, 10, 11, 12, None, 14, 15]),
        (9, [1, 2, None, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
        (10, [1, 2, None, 8, 9, 10, 11, 12, 13, 14, 15]),
        (11, [1, 2, None, 9, 10, 11, 12, 13, 14, 15]),
        (12, [1, 2, None, 10, 11, 12, 13, 14, 15]),
        (13, [1, 2, None, 11, 12, 13, 14, 15]),
        (14, [1, 2, None, 12, 13, 14, 15]),
        (15, [1, 2, None, 13, 14, 15]),
    ],
)
def test_iter_pages(page: int, expect: list[int | None]) -> None:
    p = RangePagination(page=page)
    assert list(p.iter_pages()) == expect


def test_iter_0_pages() -> None:
    p = RangePagination(total=0)
    assert list(p.iter_pages()) == []


@pytest.mark.parametrize("page", [1, 2, 3, 4])
def test_iter_pages_short(page: int) -> None:
    p = RangePagination(page=page, total=40)
    assert list(p.iter_pages()) == [1, 2, 3, 4]


class _PaginateCallable:
    def __init__(self, app: Quart, db: SQLAlchemy, Todo: t.Any) -> None:
        self.app = app
        self.db = db
        self.Todo = Todo

    async def __call__(
        self,
        page: Optional[int] = 1,
        per_page: Optional[int] = 20,
        max_per_page: Optional[int] = None,
        error_out: bool = True,
        count: bool = True,
    ) -> Pagination:
        qs = {"page": page, "per_page": per_page}
        async with self.app.test_request_context("/", query_string=qs):
            return self.db.paginate(
                self.db.select(self.Todo),
                max_per_page=max_per_page,
                error_out=error_out,
                count=count,
            )


@pytest.fixture
async def paginate(app: Quart, db: SQLAlchemy, Todo: t.Any) -> _PaginateCallable:
    async with app.app_context():
        for i in range(1, 101):
            db.session.add(Todo(title=f"task {i}"))

        db.session.commit()

    return _PaginateCallable(app, db, Todo)


async def test_paginate(paginate: _PaginateCallable) -> None:
    p = await paginate()
    assert p.page == 1
    assert p.per_page == 20
    assert len(p.items) == 20
    assert p.total == 100
    assert p.pages == 5


async def test_paginate_qs(paginate: _PaginateCallable) -> None:
    p = await paginate(page=2, per_page=10)
    assert p.page == 2
    assert p.per_page == 10


async def test_paginate_max(paginate: _PaginateCallable) -> None:
    p = await paginate(per_page=100, max_per_page=50)
    assert p.per_page == 50


async def test_no_count(paginate: _PaginateCallable) -> None:
    p = await paginate(count=False)
    assert p.total is None


@pytest.mark.parametrize(
    ("page", "per_page"), [("abc", None), (None, "abc"), (0, None), (None, -1)]
)
async def test_error_out(paginate: _PaginateCallable, page: t.Any, per_page: t.Any) -> None:
    with pytest.raises(NotFound):
        await paginate(page=page, per_page=per_page)


async def test_no_items_404(app: Quart, db: SQLAlchemy, Todo: t.Any) -> None:
    async with app.app_context():
        p = db.paginate(db.select(Todo))
        assert len(p.items) == 0

        with pytest.raises(NotFound):
            db.paginate(db.select(Todo), page=2)
