Quartr
======

The basic blog app built in the Quart `tutorial`_, modified to use
Quart-SQLAlchemy instead of plain SQL.

.. _tutorial: https://quart.palletsprojects.com/tutorial/


Install
-------

**Be sure to use the same version of the code as the version of the docs
you're reading.** You probably want the latest tagged version, but the
default Git version is the master branch.

.. code-block:: text

    # clone the repository
    $ git clone https://github.com/pallets/quart-sqlalchemy
    $ cd quart-sqlalchemy/examples/quartr
    # checkout the correct version
    $ git checkout correct-version-tag

Create a virtualenv and activate it:

.. code-block:: text

    $ python3 -m venv venv
    $ . venv/bin/activate

Or on Windows cmd:

.. code-block:: text

    $ py -3 -m venv venv
    $ venv\Scripts\activate.bat

Install Quartr:

.. code-block:: text

    $ pip install -e .

Or if you are using the master branch, install Quart-SQLAlchemy from
source before installing Quartr:

.. code-block:: text

    $ pip install -e ../..
    $ pip install -e .


Run
---

.. code-block:: text

    $ export FLASK_APP=quartr
    $ export FLASK_ENV=development
    $ quart init-db
    $ quart run

Or on Windows cmd:

.. code-block:: text

    > set FLASK_APP=quartr
    > set FLASK_ENV=development
    > quart init-db
    > quart run

Open http://127.0.0.1:5000 in a browser.


Test
----

.. code-block:: text

    $ pip install -e '.[test]'
    $ pytest

Run with coverage report:

.. code-block:: text

    $ coverage run -m pytest
    $ coverage report
    $ coverage html  # open htmlcov/index.html in a browser
