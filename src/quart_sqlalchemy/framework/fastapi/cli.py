from typing import Annotated

import typer  # type: ignore[import-not-found]

app = typer.Typer(name="db", help="Database management commands")


@app.command("info")  # type: ignore[misc]
def db_info(
    uri_only: Annotated[
        bool, typer.Option("--uri-only", help="Only output the connection URI")
    ] = False,
) -> None:
    """Display database connection information.

    Shows the database connection URI and connection parameters.
    Useful for debugging database configuration.
    """
    try:
        # Import here to avoid circular imports and to allow usage without app context
        from fastapi import FastAPI  # type: ignore[import-not-found]
        from starlette.applications import Starlette  # type: ignore[import-not-found]

        # Try to get the current app - this is tricky in FastAPI without request context
        # Users would typically call this via a custom script that has app access
        typer.echo(
            "Note: This command requires access to the FastAPI app instance.\n"
            "Please use this command from a script that has app access, e.g.:\n\n"
            "  from your_app import app\n"
            "  db = app.state.sqlalchemy\n"
            "  uri = str(db.engine.url)\n"
        )
    except ImportError:
        typer.echo("FastAPI is not installed. Please install it with: pip install fastapi")
        raise typer.Exit(1)
