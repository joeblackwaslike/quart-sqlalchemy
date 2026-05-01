import typing as t

import sqlalchemy

from quart_sqlalchemy import SQLAlchemy

from ... import base

sa = sqlalchemy


class TestExecutionOptions(base.SimpleTestBase):
    def test_yield_per(self, db: SQLAlchemy, Todo: type[t.Any]):
        with db.bind.engine.connect() as conn:
            with conn.execution_options(yield_per=2).execute(sa.select(Todo).limit(10)) as results:
                partition_count = 0
                for partition in results.partitions():
                    partition_count += 1

                    for row in partition:
                        assert row.title

                assert partition_count == 5

    def test_stream_results(self, db: SQLAlchemy, Todo: type[t.Any]):
        with db.bind.engine.connect() as conn:
            with conn.execution_options(stream_results=True).execute(sa.select(Todo)) as results:
                for row in results:
                    assert row.title
