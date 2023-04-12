import asyncio
import sys

import click
import IPython
from IPython.terminal.ipapp import load_default_config
from quart import current_app


def attach(app):
    app.shell_context_processor(app_env)
    app.cli.command(
        with_appcontext=True,
        context_settings=dict(
            ignore_unknown_options=True,
        ),
    )(ishell)


def app_env():
    app = current_app
    return dict(container=app.container)


@click.argument("ipython_args", nargs=-1, type=click.UNPROCESSED)
def ishell(ipython_args):
    import nest_asyncio

    nest_asyncio.apply()

    config = load_default_config()

    asyncio.run(current_app.startup())

    context = current_app.make_shell_context()

    config.TerminalInteractiveShell.banner1 = """Python %s on %s
IPython: %s
App: %s [%s]
""" % (
        sys.version,
        sys.platform,
        IPython.__version__,
        current_app.import_name,
        current_app.env,
    )

    IPython.start_ipython(
        argv=ipython_args,
        user_ns=context,
        config=config,
    )
