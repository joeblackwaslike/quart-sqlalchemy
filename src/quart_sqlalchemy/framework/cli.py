import json
import sys
import typing as t
import urllib.parse

import click
from quart.cli import AppGroup
from quart.cli import pass_script_info
from quart.cli import ScriptInfo

from quart_sqlalchemy import signals


if t.TYPE_CHECKING:
    from quart_sqlalchemy.framework import QuartSQLAlchemy


db_cli = AppGroup("db")
fixtures_cli = AppGroup("fixtures")


@db_cli.command("info")
@pass_script_info
@click.option("--uri-only", is_flag=True, default=False, help="Only output the connection uri")
def db_info(info: ScriptInfo, uri_only=False):
    app = info.load_app()
    db: "QuartSQLAlchemy" = app.extensions["sqlalchemy"]
    uri = urllib.parse.unquote(str(db.bind.url))
    info = dict(db.bind.url._asdict())

    if uri_only:
        click.echo(uri)
        sys.exit(0)

    click.echo("Database Connection Info")
    click.echo(json.dumps(info, indent=2))
    click.echo("\n")
    click.echo("Connection URI")
    click.echo(uri)


@db_cli.command("create")
@pass_script_info
def create(info: ScriptInfo) -> None:
    app = info.load_app()
    db: "QuartSQLAlchemy" = app.extensions["sqlalchemy"]
    db.create_all()

    click.echo(f"Initialized database schema for {db}")


@db_cli.command("drop")
@pass_script_info
def drop(info: ScriptInfo) -> None:
    app = info.load_app()
    db: "QuartSQLAlchemy" = app.extensions["sqlalchemy"]
    db.drop_all()

    click.echo(f"Dropped database schema for {db}")


@db_cli.command("recreate")
@pass_script_info
def recreate(info: ScriptInfo) -> None:
    app = info.load_app()
    db: "QuartSQLAlchemy" = app.extensions["sqlalchemy"]
    db.drop_all()
    db.create_all()

    click.echo(f"Recreated database schema for {db}")


@fixtures_cli.command("load")
@pass_script_info
def load(info: ScriptInfo) -> None:
    app = info.load_app()
    db: "QuartSQLAlchemy" = app.extensions["sqlalchemy"]
    signals.framework_extension_load_fixtures.send(sender=db, app=app)

    click.echo(f"Loaded database fixtures for {db}")


db_cli.add_command(fixtures_cli)
