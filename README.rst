Quart-SQLAlchemy
================

Quart-SQLAlchemy is an extension for `Quart`_ that adds support for
`SQLAlchemy`_ to your application. It aims to simplify using SQLAlchemy
with Quart by providing useful defaults and extra helpers that make it
easier to accomplish common tasks.


Installing
----------

Install and update using `pip`_:

.. code-block:: text

  $ pip install -U Quart-SQLAlchemy

.. _pip: https://pip.pypa.io/en/stable/getting-started/


A Simple Example
----------------

.. code-block:: python

    from quart import Quart
    from quart_sqlalchemy import SQLAlchemy

    app = Quart(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///example.sqlite"
    db = SQLAlchemy(app)


    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        username = db.Column(db.String, unique=True, nullable=False)
        email = db.Column(db.String, unique=True, nullable=False)


    db.session.add(User(username="Quart", email="example@example.com"))
    db.session.commit()

    users = User.query.all()
