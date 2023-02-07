import asyncio

from quart import Quart
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func

from quart_sqlalchemy import SQLAlchemy


def create_app():
    app = Quart(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite+aiosqlite://"
    return app


app = create_app()
db = SQLAlchemy(app, async_session=True)


class A(db.Model):
    __tablename__ = "a"

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.String)
    create_date = db.Column(db.DateTime, server_default=func.now())
    bs = db.relationship("B")


class B(db.Model):
    __tablename__ = "b"
    id = db.Column(db.Integer, primary_key=True)
    a_id = db.Column(db.ForeignKey("a.id"))
    data = db.Column(db.String)


async def async_main():
    async with app.app_context():
        async with db.engine.begin() as conn:
            print(db.metadatas)
            # await db.async_drop_all()
            # await db.async_create_all()

            await conn.run_sync(db.metadatas[None].drop_all)
            await conn.run_sync(db.metadatas[None].create_all)

        # async with db.engine.begin() as conn:
        async with db.session() as session:
            async with session.begin():

                session.add_all(
                    [
                        A(bs=[B(), B()], data="a1"),
                        A(bs=[B()], data="a2"),
                        A(bs=[B(), B()], data="a3"),
                    ]
                )
                await session.flush()

                stmt = select(A).options(selectinload(A.bs))

                results = await session.execute(stmt)
                for a in results.scalars():
                    print(a)
                    print(f"created at: {a.create_date}")
                    for b in a.bs:
                        print(b)


asyncio.run(async_main())
