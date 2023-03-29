Quart-SQLAlchemy
================

Quart-SQLAlchemy provides a simple wrapper for SQLAlchemy made for humans.  I've kept things as
simple as possible, abstracted much complexity, and implemented everything using the current
best practices recommended by the SQLAlchemy developers and targets version 2.0.x+.  As a
convenience, a framework adapter is provided for Quart, but the rest of this library is framework
agnostic.

The bundled SQLAlchemy object intentionally discards the use of scoped_session and it's async
counterpart.  With version 2.x+, it's expected that sessions are short lived and vanilla and
context managers are used for managing sesssion lifecycle.  Any operations that intend to change
state should open an explicit transaction using the context manager returned by session.begin().
This pattern of usage prevents problems like sessions being shared between processes, threads, or
tasks entirely, as opposed to the past conventions of mitigating this type of sharing.  Another
best practice is expecting any transaction to intermittently fail, and structuring your logic to
automatically perform retries.  You can find the retrying session context managers in the retry
module.

Installing
----------

Install and update using `pip`_:

.. code-block:: text

  $ pip install quart-sqlalchemy

.. _pip: https://pip.pypa.io/en/stable/getting-started/


Install the latest release with unreleased pytest-asyncio fixes:

.. code-block:: text

  $ pip install git+ssh://git@github.com/joeblackwaslike/quart-sqlalchemy.git#egg=quart_sqlalchemy

Install a wheel from our releases:

.. code-block:: text

  $ pip install https://github.com/joeblackwaslike/quart-sqlalchemy/releases/download/v3.0.1/quart_sqlalchemy-3.0.1-py3-none-any.whl


Add to requirements.txt:

.. code-block:: text

    quart-sqlalchemy @ https://github.com/joeblackwaslike/quart-sqlalchemy/releases/download/v3.0.1/quart_sqlalchemy-3.0.1-py3-none-any.whl


A Simple Example
----------------

.. code-block:: python

    import sqlalchemy as sa
    import sqlalchemy.orm
    from sqlalchemy.orm import Mapped, mapped_column
    from quart import Quart

    from quart_sqlalchemy import SQLAlchemyConfig
    from quart_sqlalchemy.framework import QuartSQLAlchemy

    app = Quart(__name__)

    db = QuartSQLAlchemy(
      config=SQLAlchemyConfig
          binds=dict(
              default=dict(
                  engine=dict(
                      url="sqlite:///",
                      echo=True,
                      connect_args=dict(check_same_thread=False),
                  ),
                  session=dict(
                      expire_on_commit=False,
                  ),
              )
          )
      ),
      app,
    )

    class User(db.Model)
        __tablename__ = "user"

        id: Mapped[int] = mapped_column(sa.Identity(), primary_key=True, autoincrement=True)
        name: Mapped[str] = mapped_column(default="default")

    db.create_all()
    
    with db.bind.Session() as s:
        with s.begin():
            user = User(username="example")
            s.add(user)
            s.flush()
            s.refresh(user)

        users = s.scalars(sa.select(User)).all()
    
    print(user, users)
    assert user in users
  
Contributing
------------

For guidance on setting up a development environment and how to make a
contribution to Quart-SQLAlchemy, see the `contributing guidelines`_.

.. _contributing guidelines: https://github.com/joeblackwaslike/quart-sqlalchemy/blob/main/CONTRIBUTING.rst
