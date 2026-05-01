# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Quart-SQLAlchemy is a framework-agnostic SQLAlchemy wrapper library targeting SQLAlchemy 2.0.x+ that follows modern best practices. While framework adapters are provided for Quart and FastAPI, the core library is intentionally framework-independent.

**Key Design Philosophy:**
- SQLAlchemy 2.0+ patterns: No scoped_session or async_scoped_session
- Short-lived sessions with explicit context managers
- Explicit transactions via `session.begin()` context managers
- Retry-first approach: Expect intermittent failures and structure logic with automatic retries
- Sessions are vanilla objects managed via context managers to prevent cross-process/thread/task sharing

## Development Environment

**Package Manager:** This project uses `uv` for dependency management and virtual environments.

```bash
# Install dependencies
uv sync

# Install with specific extras
uv sync --extra quart
uv sync --extra fastapi
uv sync --extra test
uv sync --extra dev
```

**Python Version:** Requires Python >=3.12 (supports 3.12 and 3.13)

## Common Commands

### Testing
```bash
# Run all tests with coverage
uv run python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml

# Run specific test file
uv run python -m pytest tests/integration/bind_test.py

# Run specific test
uv run python -m pytest tests/integration/bind_test.py::test_name -v

# Run with tox (tests across multiple Python versions)
tox

# Run tox for specific Python version
tox -e py312
```

### Code Quality
```bash
# Run ruff linter
uv run ruff check .

# Run ruff linter with auto-fix
uv run ruff check --fix .

# Format code with ruff
uv run ruff format .

# Type checking with mypy
uv run mypy

# Run pre-commit hooks manually
uv run pre-commit run --all-files
```

### Development
```bash
# Install pre-commit hooks
uv run pre-commit install

# Start Python shell with context (if using Quart)
# Models are auto-imported into shell context
```

## Core Architecture

### Layered Structure

1. **Core Layer (Framework-Agnostic)**
   - `sqla.py`: Main `SQLAlchemy` class - entry point for creating database connections
   - `bind.py`: `Bind` and `AsyncBind` classes - manage engine/session lifecycle for a database
   - `config.py`: Pydantic-based configuration models for engine, session, and bind settings
   - `session.py`: Enhanced `Session` and `AsyncSession` with additional utilities
   - `model/`: Base model classes and mixins (soft delete, timestamps, etc.)
   - `retry.py`: Tenacity-based retry logic for handling transient database failures

2. **Framework Adapters**
   - `framework/quart/`: Quart integration via `QuartSQLAlchemy` class
   - `framework/fastapi/`: FastAPI integration (under development)
   - Framework extensions provide CLI commands and framework-specific integrations

3. **Testing Utilities**
   - `testing/transaction.py`: `TestTransaction` and `AsyncTestTransaction` for test isolation
   - Provides rollback-based test fixtures to prevent test pollution

4. **Examples**
   - `examples/repository/`: Repository pattern implementations demonstrating best practices
   - `examples/eager_loading.py`: Examples of eager loading strategies

### Key Concepts

**Binds:** A "bind" represents a single database connection (engine + session factory). The library supports multiple named binds via the `SQLAlchemyConfig.binds` dictionary. The default bind is named "default".

**Configuration:** All configuration is done via Pydantic models:
- `SQLAlchemyConfig`: Top-level config with `binds` dictionary and `model_class`
- `BindConfig` / `AsyncBindConfig`: Per-bind configuration
- `EngineConfig`: Engine-specific settings (URL, connection args, etc.)
- `SessionmakerOptions` / `SessionOptions`: Session configuration

**Session Lifecycle:** Always use context managers for sessions and transactions:
```python
with db.bind.Session() as session:
    with session.begin():
        # Your transaction here
        pass
```

**Retry Logic:** The `retry.py` module provides retry patterns using tenacity. Structure database operations to be idempotent and use retry decorators or context managers for resilience.

**Test Transactions:** Use `TestTransaction` context manager to wrap tests in a transaction that automatically rolls back, ensuring test isolation without database cleanup.

## Code Style and Linting

- **Formatter:** Ruff (replaces Black)
- **Linter:** Ruff with extensive rule set (see `pyproject.toml` for full config)
- **Type Checker:** mypy with strict mode enabled
- **Line Length:** 100 characters
- **Docstring Style:** Google convention
- **Quote Style:** Double quotes
- **Import Sorting:** Managed by ruff (isort rules)

**Important Ruff Settings:**
- Max complexity: 24 (McCabe)
- Known first-party: `quart_sqlalchemy`, `tests`
- SQLAlchemy `declared_attr` decorators recognized as classmethods
- Test files allow asserts, hardcoded passwords, subprocess calls

**Per-file Ignores:**
- `__init__.py`: F401 (unused imports), F403 (star imports)
- `tests/*.py`: Various test-specific exceptions (see `pyproject.toml`)

## Testing Patterns

**Test Structure:**
- Unit tests in `tests/`
- Integration tests in `tests/integration/`
- Functionality tests in `tests/functionality/`
- pytest with asyncio mode set to "auto"

**Common Test Fixtures:**
- Database fixtures in `tests/conftest.py`
- Use `TestTransaction` for test isolation with automatic rollback

**Running Tests:**
- Filter warnings as errors (`filterwarnings = ["error"]` in pytest config)
- Use `-rsx --tb=short` for concise output

## Model Patterns

**Base Class:** All models should inherit from `db.Base` (or the configured `model_class`)

**Mixins Available:**
- Check `src/quart_sqlalchemy/model/mixins.py` for reusable model mixins
- Soft delete functionality available via `setup_soft_delete_for_session()`

**Type Annotations:** Use SQLAlchemy 2.0 `Mapped` typing for all columns:
```python
from sqlalchemy.orm import Mapped, mapped_column

class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column()
```

## Important Files to Review

- **Configuration patterns:** `src/quart_sqlalchemy/config.py`
- **Core bind logic:** `src/quart_sqlalchemy/bind.py`
- **Retry strategies:** `src/quart_sqlalchemy/retry.py`
- **Repository pattern examples:** `examples/repository/sqla.py`
- **Test utilities:** `src/quart_sqlalchemy/testing/transaction.py`
