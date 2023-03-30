from quart_sqlalchemy.sim.app import app
from quart_sqlalchemy.sim.views import api


app.register_blueprint(api, url_prefix="/v1")


if __name__ == "__main__":
    app.run(port=8081)
