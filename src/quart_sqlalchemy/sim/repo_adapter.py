import typing as t

import sqlalchemy
import sqlalchemy.orm
from pydantic import BaseModel
from sqlalchemy import ScalarResult
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.expression import label

from quart_sqlalchemy.model import Base
from quart_sqlalchemy.sim.repo import SQLAlchemyRepository
from quart_sqlalchemy.types import ColumnExpr
from quart_sqlalchemy.types import EntityIdT
from quart_sqlalchemy.types import EntityT
from quart_sqlalchemy.types import ORMOption
from quart_sqlalchemy.types import Selectable


sa = sqlalchemy


class BaseModelSchema(BaseModel):
    class Config:
        from_orm = True


class BaseCreateSchema(BaseModelSchema):
    pass


class BaseUpdateSchema(BaseModelSchema):
    pass


ModelSchemaT = t.TypeVar("ModelSchemaT", bound=BaseModelSchema)
CreateSchemaT = t.TypeVar("CreateSchemaT", bound=BaseCreateSchema)
UpdateSchemaT = t.TypeVar("UpdateSchemaT", bound=BaseUpdateSchema)


class RepositoryLegacyAdapter(t.Generic[EntityT, EntityIdT]):
    def __init__(
        self,
        model: t.Type[EntityT],
        identity: t.Type[EntityIdT],
        # session: Session,
    ):
        self.model = model
        self._identity = identity
        # self._session = session
        self.repo = SQLAlchemyRepository[model, identity]()

    def get_by(
        self,
        session: t.Optional[Session] = None,
        filters=None,
        allow_inactive=False,
        join_list=None,
        order_by_clause=None,
        for_update=False,
        offset=None,
        limit=None,
    ) -> t.Sequence[EntityT]:
        if filters is None:
            raise ValueError("Full table scans are prohibited. Please provide filters")

        join_list = join_list or ()

        if order_by_clause is not None:
            order_by_clause = (order_by_clause,)
        else:
            order_by_clause = ()

        return self.repo.select(
            session,
            conditions=filters,
            options=[selectinload(getattr(self.model, attr)) for attr in join_list],
            for_update=for_update,
            order_by=order_by_clause,
            offset=offset,
            limit=limit,
            include_inactive=allow_inactive,
        ).all()

    def get_by_id(
        self,
        session=None,
        model_id=None,
        allow_inactive=False,
        join_list=None,
        for_update=False,
    ) -> t.Optional[EntityT]:
        if model_id is None:
            raise ValueError("model_id is required")
        join_list = join_list or ()
        return self.repo.get(
            session,
            id_=model_id,
            options=[selectinload(getattr(self.model, attr)) for attr in join_list],
            for_update=for_update,
            include_inactive=allow_inactive,
        )

    def one(
        self, session=None, filters=None, join_list=None, for_update=False, include_inactive=False
    ) -> EntityT:
        filters = filters or ()
        join_list = join_list or ()
        return self.repo.select(
            session,
            conditions=filters,
            options=[selectinload(getattr(self.model, attr)) for attr in join_list],
            for_update=for_update,
            include_inactive=include_inactive,
        ).one()

    def count_by(
        self,
        session=None,
        filters=None,
        group_by=None,
        distinct_column=None,
    ):
        if filters is None:
            raise ValueError("Full table scans are prohibited. Please provide filters")

        group_by = group_by or ()

        if distinct_column:
            selectables = [label("count", func.count(func.distinct(distinct_column)))]
        else:
            selectables = [label("count", func.count(self.model.id))]

        for group in group_by:
            selectables.append(group.expression)

        result = self.repo.select(session, selectables, conditions=filters, group_by=group_by)

        return result.all()

    def add(self, session=None, **kwargs) -> EntityT:
        return self.repo.insert(session, kwargs)

    def update(self, session=None, model_id=None, **kwargs) -> EntityT:
        return self.repo.update(session, id_=model_id, values=kwargs)

    def update_by(self, session=None, filters=None, **kwargs) -> EntityT:
        if not filters:
            raise ValueError("Full table scans are prohibited. Please provide filters")

        row = self.repo.select(session, conditions=filters, limit=2).one()
        return self.repo.update(session, id_=row.id, values=kwargs)

    def delete_by_id(self, session=None, model_id=None) -> None:
        self.repo.delete(session, id_=model_id, include_inactive=True)

    def delete_one_by(self, session=None, filters=None, optional=False) -> None:
        filters = filters or ()
        result = self.repo.select(session, conditions=filters, limit=1)

        if optional:
            row = result.one_or_none()
            if row is None:
                return
        else:
            row = result.one()

        self.repo.delete(session, id_=row.id)

    def exist(self, session=None, filters=None, allow_inactive=False) -> bool:
        filters = filters or ()
        return self.repo.exists(
            session,
            conditions=filters,
            include_inactive=allow_inactive,
        )

    def yield_by_chunk(
        self, session=None, chunk_size=100, join_list=None, filters=None, allow_inactive=False
    ):
        filters = filters or ()
        join_list = join_list or ()
        results = self.repo.select(
            session,
            conditions=filters,
            options=[selectinload(getattr(self.model, attr)) for attr in join_list],
            include_inactive=allow_inactive,
            yield_by_chunk=chunk_size,
        )
        for result in results:
            yield result


class PydanticScalarResult(ScalarResult):
    pydantic_schema: t.Type[ModelSchemaT]

    def __init__(self, scalar_result, pydantic_schema: t.Type[ModelSchemaT]):
        for attribute in scalar_result.__slots__:
            setattr(self, attribute, getattr(scalar_result, attribute))
        self.pydantic_schema = pydantic_schema

    def _translate_many(self, rows):
        return [self.pydantic_schema.from_orm(row) for row in rows]

    def _translate_one(self, row):
        if row is None:
            return
        return self.pydantic_schema.from_orm(row)

    def all(self):
        return self._translate_many(super().all())

    def fetchall(self):
        return self._translate_many(super().fetchall())

    def fetchmany(self, *args, **kwargs):
        return self._translate_many(super().fetchmany(*args, **kwargs))

    def first(self):
        return self._translate_one(super().first())

    def one(self):
        return self._translate_one(super().one())

    def one_or_none(self):
        return self._translate_one(super().one_or_none())

    def partitions(self, *args, **kwargs):
        for partition in super().partitions(*args, **kwargs):
            yield self._translate_many(partition)


class PydanticRepository(SQLAlchemyRepository, t.Generic[EntityT, EntityIdT, ModelSchemaT]):
    @property
    def schema(self) -> t.Type[ModelSchemaT]:
        return self.__orig_class__.__args__[2]  # type: ignore

    def insert(
        self,
        session: sa.orm.Session,
        create_schema: CreateSchemaT,
        sqla_model=False,
    ):
        create_data = create_schema.dict()
        result = super().insert(session, create_data)

        if sqla_model:
            return result
        return self.schema.from_orm(result)

    def update(
        self,
        session: sa.orm.Session,
        id_: EntityIdT,
        update_schema: UpdateSchemaT,
        sqla_model=False,
    ):
        existing = session.query(self.model).get(id_)
        if existing is None:
            raise ValueError("Model not found")

        update_data = update_schema.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(existing, key, value)

        session.add(existing)
        session.flush()
        session.refresh(existing)
        if sqla_model:
            return existing
        return self.schema.from_orm(existing)

    def get(
        self,
        session: sa.orm.Session,
        id_: EntityIdT,
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        for_update: bool = False,
        include_inactive: bool = False,
        sqla_model: bool = False,
    ):
        row = super().get(
            session,
            id_,
            options,
            execution_options,
            for_update,
            include_inactive,
        )
        if row is None:
            return

        if sqla_model:
            return row
        return self.schema.from_orm(row)

    def select(
        self,
        session: sa.orm.Session,
        selectables: t.Sequence[Selectable] = (),
        conditions: t.Sequence[ColumnExpr] = (),
        group_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        order_by: t.Sequence[t.Union[ColumnExpr, str]] = (),
        options: t.Sequence[ORMOption] = (),
        execution_options: t.Optional[t.Dict[str, t.Any]] = None,
        offset: t.Optional[int] = None,
        limit: t.Optional[int] = None,
        distinct: bool = False,
        for_update: bool = False,
        include_inactive: bool = False,
        yield_by_chunk: t.Optional[int] = None,
        sqla_model: bool = False,
    ):
        result = super().select(
            session,
            selectables,
            conditions,
            group_by,
            order_by,
            options,
            execution_options,
            offset,
            limit,
            distinct,
            for_update,
            include_inactive,
            yield_by_chunk,
        )
        if sqla_model:
            return result
        return PydanticScalarResult(result, self.schema)