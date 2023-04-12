from quart_sqlalchemy.sim import commands
from quart_sqlalchemy.sim.app import create_app


app = create_app()

commands.attach(app)

if __name__ == "__main__":
    app.run(port=8081)
