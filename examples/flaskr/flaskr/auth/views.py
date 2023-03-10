import functools

from quart import Blueprint
from quart import flash
from quart import g
from quart import redirect
from quart import render_template
from quart import request
from quart import session
from quart import url_for
from quartr import db
from quartr.auth.models import User


bp = Blueprint("auth", __name__, url_prefix="/auth")


def login_required(view):
    """View decorator that redirects anonymous users to the login page."""

    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))

        return view(**kwargs)

    return wrapped_view


@bp.before_app_request
async def load_logged_in_user():
    """If a user id is stored in the session, load the user object from
    the database into ``g.user``."""
    user_id = session.get("user_id")

    if user_id is not None:
        g.user = await db.session.get(User, user_id)
    else:
        g.user = None


@bp.route("/register", methods=("GET", "POST"))
async def register():
    """Register a new user.

    Validates that the username is not already taken. Hashes the
    password for security.
    """
    if request.method == "POST":
        username = (await request.form)["username"]
        password = (await request.form)["password"]
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."
        elif (
            await db.session.execute(
                db.select(db.select(User).filter_by(username=username).exists())
            )
        ).scalar():
            error = f"User {username} is already registered."

        if error is None:
            # the name is available, create the user and go to the login page
            db.session.add(User(username=username, password=password))
            await db.session.commit()
            return redirect(url_for("auth.login"))

        await flash(error)

    return await render_template("auth/register.html")


@bp.route("/login", methods=("GET", "POST"))
async def login():
    """Log in a registered user by adding the user id to the session."""
    if request.method == "POST":
        username = (await request.form)["username"]
        password = (await request.form)["password"]
        error = None
        select = db.select(User).filter_by(username=username)
        user = (await db.session.execute(select)).scalar()

        if user is None:
            error = "Incorrect username."
        elif not user.check_password(password):
            error = "Incorrect password."

        if error is None:
            # store the user id in a new session and return to the index
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("index"))

        await flash(error)

    return await render_template("auth/login.html")


@bp.route("/logout")
def logout():
    """Clear the current session, including the stored user id."""
    session.clear()
    return redirect(url_for("index"))
