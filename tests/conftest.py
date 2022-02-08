from datetime import datetime

import pytest
import quart

from quart_sqlalchemy import SQLAlchemy


@pytest.fixture
def app(request):
    app_ = quart.Quart(request.module.__name__)
    app_.testing = True
    app_.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    # async with app_.test_app():
    yield app_


@pytest.fixture
def db(app):
    yield SQLAlchemy(app)


@pytest.fixture
def Todo(db):
    class Todo(db.Model):
        __tablename__ = "todos"
        id = db.Column("todo_id", db.Integer, primary_key=True)
        title = db.Column(db.String(60))
        text = db.Column(db.String)
        done = db.Column(db.Boolean)
        pub_date = db.Column(db.DateTime)

        def __init__(self, title, text):
            self.title = title
            self.text = text
            self.done = False
            self.pub_date = datetime.utcnow()

    db.create_all()
    yield Todo
    db.drop_all()
