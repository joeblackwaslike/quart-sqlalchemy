Quart-SQLAlchemy
================

Quart-SQLAlchemy is an extension for `Quart` that adds support for
`SQLAlchemy` to your application. It aims to simplify using SQLAlchemy
with Quart by providing useful defaults and extra helpers that make it
easier to accomplish common tasks.

This work is based on the excellent Flask extension [FlaskSQLAlchemy](https://github.com/pallets-eco/flask-sqlalchemy/tree/main/examples)
and is essentialy a port of that to Quart.


Installing
----------

Install and update using `pip`_:

.. code-block:: text

  $ pip install -U quart-sqlalchemy

.. _pip: https://pip.pypa.io/en/stable/getting-started/


A Simple Example
----------------

.. code-block:: python

    from quart import Quart
    from quart_sqlalchemy import SQLAlchemy

    app = Quart(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///example.sqlite"
    db = SQLAlchemy(app)

    class User(db.Model)
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String, unique=True, nullable=False)

    with app.app_context():
        db.create_all()

        db.session.add(User(username="example"))
        db.session.commit()

        users = db.session.execute(db.select(User)).scalars()


Contributing
------------

For guidance on setting up a development environment and how to make a
contribution to Quart-SQLAlchemy, see the `contributing guidelines`_.

.. _contributing guidelines: https://github.com/joeblackwaslike/quart-sqlalchemy/blob/main/CONTRIBUTING.rst


Donate
------

The Pallets organization develops and supports Flask-SQLAlchemy and
other popular packages. In order to grow the community of contributors
and users, and allow the maintainers to devote more time to the
projects, `please donate today`_.

.. _please donate today: https://palletsprojects.com/donate


Links
-----

-   Documentation: 
-   Changes: 
-   PyPI Releases: https://pypi.org/project/
-   Source Code: https://github.com/joeblackwaslike/quart-sqlalchemy/
-   Issue Tracker: https://github.com/joeblackwaslike/quart-sqlalchemy/issues/
-   Website: 
-   Twitter: 
-   Chat: 
