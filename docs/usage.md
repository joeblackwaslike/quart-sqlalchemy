# API

## SQLAlchemy
### `quart_sqlalchemy.sqla.SQLAlchemy`

### Conventions
This manager class keeps things very simple by using a few configuration conventions:

* Configuration has been simplified down to base_class and binds.
* Everything related to ORM mapping, DeclarativeBase, registry, MetaData, etc should be configured by passing the a custom DeclarativeBase class as the base_class configuration parameter.
* Everything related to engine/session configuration should be configured by passing a dictionary mapping string names to BindConfigs as the `binds` configuration parameter.
* the bind named `default` is the canonical bind, and to be used unless something more specific has been requested
  
### Configuration
BindConfig can be as simple as a dictionary containing a url key like so:
```python
bind_config = {
    "default": {"url": "sqlite://"}
}
```

But most use cases will require more than just a connection url, and divide core/engine configuration from orm/session configuration which looks more like this:
```python
bind_config = {
    "default": {
        "engine": {
            "url": "sqlite://"
        },
        "session": {
            "expire_on_commit": False
        }
    }
}
```
    
It helps to think of the bind configuration as being the options dictionary used to build the main core and orm factory objects.
* For SQLAlchemy core, the configuration under the key `engine` will be used by `sa.engine_from_config` to build the `sa.Engine` object which acts as a factory for `sa.Connection` objects. 
  ```python
   engine = sa.engine_from_config(config.engine, prefix="")
  ```
* For SQLAlchemy orm, the configuration under the key `session` will be used  to build the `sa.orm.sessionmaker` session factory which acts as a factory for `sa.orm.Session` objects.
  ```python
   session_factory = sa.orm.sessionmaker(bind=engine, **config.session)
  ```

#### Usage Examples
SQLAlchemyConfig is to be passed to SQLAlchemy or QuartSQLAlchemy as the first parameter when initializing.

```python    
db = SQLAlchemy(
    SQLAlchemyConfig(
        binds=dict(
            default=dict(
                url="sqlite://"
            )
        )
    )
)
```

When nothing is provided to SQLAlchemyConfig directly, it is instantiated with the following defaults

```python
db = SQLAlchemy(SQLAlchemyConfig())
```

For `QuartSQLAlchemy` configuration can also be provided via Quart configuration.
```python
from quart_sqlalchemy.framework import QuartSQLAlchemy

app = Quart(__name__)
app.config.from_mapping(
    {
        "SQLALCHEMY_BINDS": {
            "default": {
                "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
                "session": {"expire_on_commit": False},
            }
        },
        "SQLALCHEMY_BASE_CLASS": Base,
    }
)
db = QuartSQLAlchemy(app=app)
```




A typical configuration containing engine and session config both:
```python
config = SQLAlchemyConfig(
    binds=dict(
        default=dict(
            engine=dict(
                url="sqlite://"
            ),
            session=dict(
                expire_on_commit=False
            )
        )
    )
)
```

Async first configuration
```python
config = SQLAlchemyConfig(
    binds=dict(
        default=dict(
            engine=dict(
                url="sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"
            ),
            session=dict(
                expire_on_commit=False
            )
        )
    )
)
```

More complex configuration having two additional binds based on default, one for a read-replica and the second having an async driver 

```python
config = {
    "SQLALCHEMY_BINDS": {
        "default": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        },
        "read-replica": {
            "engine": {"url": "sqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
            "read_only": True,
        },
        "async": {
            "engine": {"url": "sqlite+aiosqlite:///file:mem.db?mode=memory&cache=shared&uri=true"},
            "session": {"expire_on_commit": False},
        },
    },
    "SQLALCHEMY_BASE_CLASS": Base,
}
```


    Once instantiated, operations targetting all of the binds, aka metadata, like
    `metadata.create_all` should be called from this class.  Operations specific to a bind
    should be called from that bind.  This class has a few ways to get a specific bind.

    * To get a Bind, you can call `.get_bind(name)` on this class.  The default bind can be
    referenced at `.bind`.

    * To define an ORM model using the Base class attached to this class, simply inherit
    from `.Base`

        db = SQLAlchemy(SQLAlchemyConfig())

        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()

    * You can also decouple Base from SQLAlchemy with some dependency inversion:
        from quart_sqlalchemy.model.mixins import DynamicArgsMixin, ReprMixin, TableNameMixin

        class Base(DynamicArgsMixin, ReprMixin, TableNameMixin):
            __abstract__ = True


        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db = SQLAlchemy(SQLAlchemyConfig(bind_class=Base))

        db.create_all()


    Declarative Mapping using registry based decorator:

        db = SQLAlchemy(SQLAlchemyConfig())

        @db.registry.mapped
        class User(db.Base):
            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Declarative with Imperative Table (Hybrid Declarative):

        class User(db.Base):
            __table__ = sa.Table(
                "user",
                db.metadata,
                sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
                sa.Column("name", sa.String, default="Joe"),
            )


    Declarative using reflection to automatically build the table object:

    class User(db.Base):
        __table__ = sa.Table(
            "user",
            db.metadata,
            autoload_with=db.bind.engine,
        )


    Declarative Dataclass Mapping:

        from quart_sqlalchemy.model import Base as Base_

        class Base(sa.orm.MappedAsDataclass, Base_):
            pass

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        class User(db.Base):
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Declarative Dataclass Mapping (using decorator):

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        @db.registry.mapped_as_dataclass
        class User:
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()


    Alternate Dataclass Provider Pattern:

        from pydantic.dataclasses import dataclass
        from quart_sqlalchemy.model import Base as Base_

        class Base(sa.orm.MappedAsDataclass, Base_, dataclass_callable=dataclass):
            pass

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        class User(db.Base):
            __tablename__ = "user"

            id: Mapped[int] = sa.orm.mapped_column(primary_key=True, autoincrement=True)
            name: Mapped[str] = sa.orm.mapped_column(default="Joe")

        db.create_all()

    Imperative style Mapping

        db = SQLAlchemy(SQLAlchemyConfig(base_class=Base))

        user_table = sa.Table(
            "user",
            db.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String, default="Joe"),
        )

        post_table = sa.Table(
            "post",
            db.metadata,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("title", sa.String, default="My post"),
            sa.Column("user_id", sa.ForeignKey("user.id"), nullable=False),
        )

        class User:
            pass

        class Post:
            pass

        db.registry.map_imperatively(
            User,
            user_table,
            properties={
                "posts": sa.orm.relationship(Post, back_populates="user")
            }
        )
        db.registry.map_imperatively(
            Post,
            post_table,
            properties={
                "user": sa.orm.relationship(User, back_populates="posts", uselist=False)
            }
        )