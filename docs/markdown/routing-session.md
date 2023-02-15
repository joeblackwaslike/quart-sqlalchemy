# Routing Session
## Introduction
This feature allow `session`s issued by `SQLAlchemy` to target at runtime a specific `bind` for execution by providing it's `bind_key`.

SQLAlchemy supports the configuration of multiple binds, but by default only supports multiple binds for the use case of defining models that are specific to only one of those binds, expressed through class `__bind_key__` attribute of the model, which defaults to (None).

In order to support more interesting use cases for binds, such as read-write masters, read-only replicas, etc, a solution was devised where you could very easily select an alternative bind for an already existing bound session.

## Use cases
* read-write master
* read-only replica
* geo-distributed replication / isolation for replication or enforcing strict data residency compliance measures.
* write-through, write-beind, write-before, caching implementations
* Create a new bind from an existing bind but with different engine, execution, and connection arguments such as: autocommit, autobegin, and transaction_isolation level. While this would require defining the bind before hand, you can also achieve this behavior at runtime by using another new feature called [Bind Contexts](bind-contexts.md).
* 

## Usage
Below is a brief example of how to configure SQLAlchemy for multiple binds.  The example below utilizes sqlite uri strings to define a few seperate binds that all share the same in-memory virtual database, so changes made in the default (None) bind will be available in the others  To be clear, no files will be created, this is a virtual construct available only within the sqlite dialect.

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

Using routing session we can execute the same operations on a specific bind by using the method `RoutingSession.using_bind`.  Note that by design, `using_bind` should be the first call in the the `Session` call chain to set the appropriate context as early as possible.  Using it later in the call chain is not a tested or supported use case.


```python
async with app.app_context():   
    assert len(db.session.using_bind("read-replica").scalars(select(Todo)).all()) == 1
```
