from sqlalchemy import exists
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.expression import label


def one(input_list):
    (item,) = input_list
    return item


class SQLRepository:
    def __init__(self, model):
        self._model = model
        assert self._model is not None

    @property
    def _has_is_active_field(self):
        return bool(getattr(self._model, "is_active", None))

    def get_by_id(
        self,
        session,
        model_id,
        allow_inactive=False,
        join_list=None,
        for_update=False,
    ):
        """SQL get interface to retrieve by model's id column.

        Args:
            session: A database session object.
            model_id: The id of the given model to be retrieved.
            allow_inactive: Whether to include inactive or not.
            join_list: A list of attributes to be joined in the same session for
                        given model. This is normally the attributes that have
                        relationship defined and referenced to other models.
            for_update: Locks the table for update.

        Returns:
            Data retrieved from the database for the model.
        """
        query = session.query(self._model)

        if join_list:
            for to_join in join_list:
                query = query.options(joinedload(to_join))

        if for_update:
            query = query.with_for_update()

        row = query.get(model_id)

        if row is None:
            return None

        if self._has_is_active_field and not row.is_active and not allow_inactive:
            return None

        return row

    def get_by(
        self,
        session,
        filters=None,
        join_list=None,
        order_by_clause=None,
        for_update=False,
        offset=None,
        limit=None,
    ):
        """SQL get_by interface to retrieve model instances based on the given
        filters.

        Args:
            session: A database session object.
            filters: A list of filters on the models.
            join_list: A list of attributes to be joined in the same session for
                        given model. This is normally the attributes that have
                        relationship defined and referenced to other models.
            order_by_clause: An order by clause.
            for_update: Locks the table for update.

        Returns:
            Modified rows.

        TODO(ajen#ch21549|2020-07-21): Filter out `is_active == False` row. This
        will not be a trivial change as many places rely on this method and the
        handlers/logics sometimes filter by in_active. Sometimes endpoints might
        get affected. Proceed with caution.
        """
        # If no filter is given, just return. Prevent table scan.
        if filters is None:
            return None

        query = session.query(self._model).filter(*filters).order_by(order_by_clause)

        if for_update:
            query = query.with_for_update()

        if offset:
            query = query.offset(offset)

        if limit:
            query = query.limit(limit)

        # Prevent loading all the rows.
        if limit == 0:
            return []

        if join_list:
            for to_join in join_list:
                query = query.options(joinedload(to_join))

        return query.all()

    def count_by(
        self,
        session,
        filters=None,
        group_by=None,
        distinct_column=None,
    ):
        """SQL count_by interface to retrieve model instance count based on the given
        filters.

        Args:
            session: A database session object.
            filters (list): Required; a list of filters on the models.
            group_by (list): A list of optional group by expressions.
        Returns:
            A list of counts of rows.
        Raises:
            ValueError: Returns a value error, when no filters are provided
        """
        # Prevent table scans
        if filters is None:
            raise ValueError("Full table scans are prohibited. Please provide filters")

        select = [label("count", func.count(self._model.id))]

        if distinct_column:
            select = [label("count", func.count(func.distinct(distinct_column)))]

        if group_by:
            for group in group_by:
                select.append(group.expression)

        query = session.query(*select).filter(*filters)

        if group_by:
            query = query.group_by(*group_by)

        return query.all()

    def sum_by(
        self,
        session,
        column,
        filters=None,
        group_by=None,
    ):
        """SQL sum_by interface to retrieve aggregate sum of column values for given
        filters.

        Args:
            session: A database session object.
            column (sqlalchemy.Column): Required; the column to sum by.
            filters (list): Required; a list of filters to apply to the query
            group_by (list): A list of optional group by expressions.

        Returns:
            A scalar value representing the sum or None.

        Raises:
            ValueError: Returns a value error, when no filters are provided
        """

        # Prevent table scans
        if filters is None:
            raise ValueError("Full table scans are prohibited. Please provide filters")

        query = session.query(func.sum(column)).filter(*filters)

        if group_by:
            query = query.group_by(*group_by)

        return query.scalar()

    def one(self, session, filters=None, join_list=None, for_update=False):
        """SQL filtering interface to retrieve the single model instance matching
        filter criteria.

        If there are more than one instances, an exception is raised.

        Args:
            session: A database session object.
            filters: A list of filters on the models.
            for_update: Locks the table for update.

        Returns:
            A model instance: If one row is found in the db.
            None: If no result is found.
        """
        row = self.get_by(session, filters=filters, join_list=join_list, for_update=for_update)

        if not row:
            return None

        return one(row)

    def update(self, session, model_id, **kwargs):
        """SQL update interface to modify data in a given model instance.

        Args:
            session: A database session object.
            model_id: The id of the given model to be modified.
            kwargs: Any fields defined on the models.

        Returns:
            Modified rows.

        Note:
            We use session.flush() here to move the changes from the application
            to SQL database. However, those changes will be in the pending changes
            state. Meaning, it is in the queue to be inserted but yet to be done
            so until session.commit() is called, which has been taken care of
            in our ``with_db_session`` decorator or ``LogicComponent.begin``
            contextmanager.
        """
        modified_row = session.query(self._model).get(model_id)
        if modified_row is None:
            return None

        for key, value in kwargs.items():
            setattr(modified_row, key, value)

        # Flush out our changes to DB transaction buffer but don't commit it yet.
        # This is useful in the case when we want to rollback atomically on multiple
        # sql operations in the same transaction which may or may not have
        # dependencies.
        session.flush()

        return modified_row

    def update_by(self, session, filters=None, **kwargs):
        """SQL update_by interface to modify data for a given list of filters.
        The filters should be provided so it can narrow down to one row.

        Args:
            session: A database session object.
            filters: A list of filters on the models.
            kwargs: Any fields defined on the models.

        Returns:
            Modified row.

        Raises:
            sqlalchemy.orm.exc.NoResultFound - when no result is found.
            sqlalchemy.orm.exc.MultipleResultsFound - when multiple result is found.
        """
        # If no filter is given, just return. Prevent table scan.
        if filters is None:
            return None

        modified_row = session.query(self._model).filter(*filters).one()
        for key, value in kwargs.items():
            setattr(modified_row, key, value)

        # Flush out our changes to DB transaction buffer but don't commit it yet.
        # This is useful in the case when we want to rollback atomically on multiple
        # sql operations in the same transaction which may or may not have
        # dependencies.
        session.flush()

        return modified_row

    def delete_one_by(self, session, filters=None, optional=False):
        """SQL update_by interface to delete data for a given list of filters.
        The filters should be provided so it can narrow down to one row.

        Note: Careful consideration should be had prior to using this function.
        Always consider setting rows as inactive instead before choosing to use
        this function.

        Args:
            session: A database session object.
            filters: A list of filters on the models.
            optional: Whether deletion is optional; i.e. it's OK for the model not to exist

        Returns:
            None.

        Raises:
            sqlalchemy.orm.exc.NoResultFound - when no result is found and optional is False.
            sqlalchemy.orm.exc.MultipleResultsFound - when multiple result is found.
        """
        # If no filter is given, just return. Prevent table scan.
        if filters is None:
            return None

        if optional:
            rows = session.query(self._model).filter(*filters).all()

            if not rows:
                return None

            row = one(rows)

        else:
            row = session.query(self._model).filter(*filters).one()

        session.delete(row)

        # Flush out our changes to DB transaction buffer but don't commit it yet.
        # This is useful in the case when we want to rollback atomically on multiple
        # sql operations in the same transaction which may or may not have
        # dependencies.
        session.flush()

    def delete_by_id(self, session, model_id):
        return session.query(self._model).get(model_id).delete()

    def add(self, session, **kwargs):
        """SQL add interface to insert data to the given model.

        Args:
            session: A database session object.
            kwargs: Any fields defined on the models.

        Returns:
            Newly inserted rows.

        Note:
            We use session.flush() here to move the changes from the application
            to SQL database. However, those changes will be in the pending changes
            state. Meaning, it is in the queue to be inserted but yet to be done
            so until session.commit() is called, which has been taken care of
            in our ``with_db_session`` decorator or ``LogicComponent.begin``
            contextmanager.
        """
        new_row = self._model(**kwargs)
        session.add(new_row)

        # Flush out our changes to DB transaction buffer but don't commit it yet.
        # This is useful in the case when we want to rollback atomically on multiple
        # sql operations in the same transaction which may or may not have
        # dependencies.
        session.flush()

        return new_row

    def exist(self, session, filters=None):
        """SQL exist interface to check if any row exists at all for the given
        filters.

        Args:
            session: A database session object.
            filters: A list of filters on the models.

        Returns:
            A boolean. True if any row exists else False.
        """
        exist_query = exists()

        for query_filter in filters:
            exist_query = exist_query.where(query_filter)

        return session.query(exist_query).scalar()

    def yield_by_chunk(self, session, chunk_size, join_list=None, filters=None):
        """This yields a batch of the model objects for the given chunk_size.

        Args:
            session: A database session object.
            chunk_size (int): The size of the chunk.
            filters: A list of filters on the model.
            join_list: A list of attributes to be joined in the same session for
                given model. This is normally the attributes that have
                relationship defined and referenced to other models.

        Returns:
            A batch for the given chunk size.
        """
        query = session.query(self._model)

        if filters is not None:
            query = query.filter(*filters)

        if join_list:
            for to_join in join_list:
                query = query.options(joinedload(to_join))

        start = 0

        while True:
            stop = start + chunk_size
            model_objs = query.slice(start, stop).all()
            if not model_objs:
                break

            yield model_objs

            start += chunk_size
