from quart_sqlalchemy.sim.app import create_app


app = create_app()


if __name__ == "__main__":
    app.run(port=8081)
