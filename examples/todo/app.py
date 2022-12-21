from datetime import datetime
from datetime import timezone
import asyncio

from quart import flash
from quart import Quart
from quart import redirect
from quart import render_template
from quart import request
from quart import url_for
from quart_sqlalchemy import SQLAlchemy

app = Quart(__name__)
app.secret_key = "Achee6phIexoh8dagiQuew0ephuga4Ih"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todo.sqlite"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app, engine_options=dict(check_same_thread=False))


def now_utc():
    return datetime.now(timezone.utc)


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    text = db.Column(db.String, nullable=False)
    done = db.Column(db.Boolean, nullable=False, default=False)
    pub_date = db.Column(db.DateTime, nullable=False, default=now_utc)


@app.route("/")
async def show_all():
    select = db.select(Todo).order_by(Todo.pub_date.desc())
    todos = db.session.execute(select).all()
    # import pdb; pdb.set_trace()
    return dict(status='ok', todos=len(todos))
    # return await render_template("show_all.html", todos=todos)


@app.route("/new", methods=["GET", "POST"])
async def new():
    if request.method == "POST":
        form = await request.form
        if not form["title"]:
            await flash("Title is required", "error")
        elif not form["text"]:
            await flash("Text is required", "error")
        else:
            todo = Todo(title=form["title"], text=form["text"])
            db.session.add(todo)
            db.session.commit()
            await flash("Todo item was successfully created")
            return redirect(url_for("show_all"))

    return await render_template("new.html")


@app.route("/update", methods=["POST"])
async def update_done():
    form = await request.form

    for todo in db.session.execute(db.select(Todo)).scalars():
        todo.done = f"done.{todo.id}" in form

    await flash("Updated status")
    db.session.commit()
    return redirect(url_for("show_all"))


async def setup_db():
    async with app.app_context():
        db.create_all()


if __name__ == "__main__":
    asyncio.run(setup_db())