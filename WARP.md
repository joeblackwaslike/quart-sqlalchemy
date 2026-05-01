# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Repository Overview

**quart-sqlalchemy** is a modern SQLAlchemy 2.0+ wrapper library with a framework adapter for Quart. The library emphasizes best practices including short-lived sessions, explicit transactions, and configuration-driven architecture. It's designed to be framework-agnostic at its core with specific adapters for web frameworks.

## Common Development Commands

### Environment Setup
```sh
# Install dependencies with development extras
uv sync --extra dev
```

### Testing
```sh
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/integration/bind_test.py

# Run tests with coverage
uv run pytest --cov --cov-config=pyproject.toml --cov-report=xml

# Run tests across multiple Python versions
tox
```

### Code Quality
```sh
# Run all linting and formatting
uv run pre-commit run --all-files

# Just run ruff for formatting and linting
uv run ruff check .
uv run ruff format .

# Run type checking
uv run mypy
```

### Database Management
```sh
# Create all tables (when using db instance)
db.create_all()

# Drop all tables
db.drop_all()

# Using specific bind
db.create_all(bind="secondary")
```

## High-Level Architecture

### Core Module Structure

- **`bind.py`** - Database bind management with sync/async support, connection pooling, and cross-process safety
- **`config.py`** - Pydantic-based configuration system with comprehensive SQLAlchemy settings validation
- **`session.py`** - Enhanced Session classes with convenience methods (get_or_404, paginate)
- **`retry.py`** - Transaction retry mechanisms using tenacity for handling transient database errors
- **`sqla.py`** - Core SQLAlchemy wrapper providing framework-agnostic database management
- **`framework/`** - Framework-specific adapters (currently Quart extension)
- **`model/`** - Rich collection of model mixins and utilities (TimestampMixin, SoftDeleteMixin, etc.)

### Configuration Architecture

The library uses a hierarchical Pydantic configuration system:

```python
SQLAlchemyConfig
├── model_class: Base model class
└── binds: dict[str, BindConfig | AsyncBindConfig]
    ├── engine: EngineConfig (URL, pooling, execution options)
    └── session: SessionmakerOptions (autoflush, expire settings)
```

### Multi-Bind Support

Supports multiple database connections with different configurations:
- **Sync/Async binds** - Can mix synchronous and asynchronous database connections
- **Read-only binds** - Separate read replicas for query optimization
- **Named binds** - Reference specific databases by name (e.g., "analytics", "cache")

### Framework Integration Pattern

The core `SQLAlchemy` class is framework-agnostic. Framework-specific features are added through adapters:
- `QuartSQLAlchemy` extends core functionality with Quart-specific features
- Signal system (`signals.py`) provides extensibility hooks
- CLI commands and shell context processors are framework-specific

### Testing Architecture

- **Base test classes** - `SimpleTestBase`, `AsyncTestBase`, `ComplexTestBase` for different scenarios
- **Fixture management** - Automatic database setup/teardown with model creation
- **Multi-environment testing** - Tox configuration for Python 3.10-3.13

## Key Development Patterns

### Session Management Best Practices
```python
# Explicit transaction with context manager
with db.bind.Session() as session:
    with session.begin():
        # All database operations here
        session.add(model_instance)
        session.flush()
        session.refresh(model_instance)
# Automatic rollback on exception, commit on success
```

### Configuration Usage
```python
# Framework-agnostic usage
config = SQLAlchemyConfig(
    binds=dict(
        default=BindConfig(
            engine=EngineConfig(url="sqlite:///app.db"),
            session=SessionmakerOptions(expire_on_commit=False)
        )
    )
)
db = SQLAlchemy(config)

# With Quart framework
app = Quart(__name__)
db = QuartSQLAlchemy(config, app)
```

### Model Definition Patterns
```python
class User(db.Model):
    __tablename__ = "users"
    
    id: Mapped[int] = sa.orm.mapped_column(primary_key=True)
    username: Mapped[str] = sa.orm.mapped_column()
    
    # Use provided mixins for common patterns
    # TimestampMixin adds created_at, updated_at
    # SoftDeleteMixin adds deleted_at with query filtering
```

### Error Handling and Retries
```python
# Using retry decorators
@tenacity.retry(**retry_config)
def database_operation():
    with db.bind.Session() as session:
        with session.begin():
            # Operations that might need retry
            pass

# Using retry context managers
try:
    for attempt in tenacity.Retrying(**retry_config):
        with attempt:
            # Database operations here
            pass
except tenacity.RetryError:
    # Handle final failure
    pass
```

## Important Implementation Details

### Cross-Process Safety
The library automatically handles SQLAlchemy connection sharing issues in multi-process environments (ASGI servers, pytest-xdist) through event listeners that dispose connections on process fork.

### Database Driver Optimizations
- **SQLite**: Automatic transaction fixes for pysqlite driver limitations
- **MySQL**: Connection pre-ping and charset defaults
- **Connection pooling**: Smart defaults based on database type

### Type Safety
Extensive use of generics and Pydantic models ensures type safety throughout the configuration and session management layers.

### Async Support
Full async/await support through `AsyncBind` and `AsyncSession` classes with proper sync/async sessionmaker integration for SQLAlchemy events.
