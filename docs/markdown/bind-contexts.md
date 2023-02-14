# Bind Contexts
## Introduction
The concept of a "Bind Context" has been added to Quart-SQLAlchemy to better support multiple engines without making major breaking API changes to `SQLAlchemy`.

As an example, a SQLAlchemy object has the following properties:
* `db.engine` -> returns the `Engine` object for the default (None) bind
* `db.metadata` -> returns the `MetaData` object for the default (None) bind
* `db.session` -> returns a `scoped_session` object that defaults to (None) bind

SQLAlchemy supports the configuration of multiple binds, but by default only supports multiple binds for the use case of defining models that are specific to only one of those binds, expressed through class `__bind_key__` attribute of the model, which defaults to (None).

In order to support more interesting use cases, such as read-write masters, read-only replicas, and async replicas, a solution was devised where you could temporarily enter a bind context for a given `bind_key` and the object returned would very much resemble the `SQLAlchemy` API in regards to `ctx.engine`, `ctx.metadata`, `ctx.session` but scoped to the provided `bind_key` instead of default (None).

## Usage
Below is a brief example of configuring SQLAlchemy for multiple binds.  The example below utilizes sqlite uri strings to define three seperate binds that all share the same in-memory virtual database, so changes made in the default (None) bind will be available in "read-replica" and "async".  To be clear, no files will be created, this is a virtual construct available only within the sqlite dialect.

```python
config = {
    "SQLALCHEMY_BINDS": {
        None: dict(
            url="sqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "replica": dict(
            url="sqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
        "async": dict(
            url="sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true",
            connect_args=dict(check_same_thread=False),
        ),
    },
}

app = Quart(__name__)
app.config.from_mapping(config)
db = SQLAlchemy(app)


class Todo(db.Model):
    Mapped[int] = sa.orm.mapped_column(primary_key=True)


async with app.app_context():
    db.create_all(None)
```

Adding a single Todo to the default bind.
```python
async with app.app_context():
    db.session.add(Todo())
    db.session.commit()
    assert len(db.session.scalars(select(Todo)).all()) == 1
```
Using bind contexts we can execute the same operations just as easily on binds other than default simply by passing their key to `db.bind_context()`.

Adding another Todo through 'replica':
```python
async with app.app_context():   
    with db.bind_context('replica') as ctx:
        ctx.session.add(Todo())
        ctx.session.commit()
        assert len(ctx.session.scalars(select(Todo)).all()) == 2
```

Adding another Todo through 'async':
```python
async with app.app_context():   
    async with db.bind_context('async') as ctx: # BindContext supports both with and async with depending on whether the underlying engine is Async or not.
        ctx.session.add(Todo())
        await ctx.session.commit()
        assert len((await ctx.session.scalars(select(Todo))).all()) == 2
```
***Note the `async` and `await` keywords that have been added to `db.bind_context`, `session.commit`, and `session.scalars`.***

### Using bind context to temporarily enter a different transaction isolation level
There are number of use cases where one may want to temporarily enter into a different transaction isolation level.  Support for this is built into `bind_context` in the form of the `execution_options` parameter.  The result is that `ctx.engine` is a shallow clone of the engine for the requested `bind_key` with the contents of `execution_options` applied.

**Isolation levels:**
* `AUTOCOMMIT`
* `READ COMMITTED`
* `READ UNCOMMITTED`
* `REPEATABLE READ`
* `SERIALIZABLE`

**Requesting a `bind_context` with `SERIALIZABLE` `isolation_level`:**
```python
async with app.app_context():
    with db.bind_context(
        None,
        execution_options=dict(isolation_level="SERIALIZABLE"),
    ) as ctx.
        with ctx.connection.begin():
            ctx.connection.execute("statement")
```

## API
### `SQLAlchemy.bind_context`
```python
def bind_context(
    self,
    bind_key: Optional[str] = None,
    execution_options: Optional[dict[str, Any]] = None,
    app: Optional[Quart] = None,
) -> BindContext:
    ...
```
`SQLAlchemy.bind_context` accepts an optional `app` parameter.  When provided, the `BindContext` returned will resolve the correct `engine` using the provided `app` object rather than first attempting to resolve it using the `Quart.current_app` proxy.  This option has very few compelling use cases, most of which occur during usage in a shell such as IPython or integration tests.


### `BindContext`
This is the API of the object returned by `SQLAlchemy.bind_context`.  As mentioned, it implements the essential database functionality often provided by the `SQLAlchemy`or `db` object for the given `bind_key`.
```python
class BindContext:
    bind_key: Optional[str]
    is_async: bool
    execution_options: dict[str, Any]
    engine: Engine | AsyncEngine
    metadata: MetaData
    connection: Connection | AsyncConnection
    session: scoped_session | async_scoped_session
```

`BindContext` supports the context manager protocol as well as the async context manager protocol.  If you request a synchronous bind, you should enter the context using `with`, if you request an asynchronous bind, you should enter the context using `async with`.