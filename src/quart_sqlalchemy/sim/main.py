from .app import app
from .views import api


app.register_blueprint(api)


if __name__ == "__main__":
    app.run(port=8080)
