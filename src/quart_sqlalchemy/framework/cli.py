import json
import sys
import urllib.parse

import click
from quart import current_app
from quart.cli import AppGroup


db_cli = AppGroup("db")


@db_cli.command("info", with_appcontext=True)
@click.option("--uri-only", is_flag=True, default=False, help="Only output the connection uri")
def db_info(uri_only=False):
    db = current_app.extensions["sqlalchemy"].db
    uri = urllib.parse.unquote(str(db.engine.url))
    db_info = dict(db.engine.url._asdict())

    if uri_only:
        click.echo(uri)
        sys.exit(0)

    click.echo("Database Connection Info")
    click.echo(json.dumps(db_info, indent=2))
    click.echo("\n")
    click.echo("Connection URI")
    click.echo(uri)
