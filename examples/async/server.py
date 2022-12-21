import asyncio

from quart import Quart
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import func

from quart_sqlalchemy import SQLAlchemy


def create_app():
    app = Quart(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite+aiosqlite:///:memory:"
    app.config["SQLALCHEMY_ENGINE_ASYNC"] = True
    return app


app = create_app()
db = SQLAlchemy(app)


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
    import pdb

    pdb.set_trace()
    async with app.app_context():
        async with db.engine.begin() as conn:
            await conn.run_sync(db.metadata.drop_all)
            await conn.run_sync(db.metadata.create_all)

        # async with db.engine.begin() as conn:
        async with db.session() as session:
            async with session.begin():
                session.add(A(bs=[B(), B()], data="a1"))
                # session.add_all(
                #     [
                #         A(bs=[B(), B()], data="a1"),
                #         A(bs=[B()], data="a2"),
                #         A(bs=[B(), B()], data="a3"),
                #     ]
                # )
                await session.commit()
                # await session.commit()

    # async with app.app_context():
    #         stmt = select(A).options(selectinload(A.bs))

    #         result = await session.execute(stmt)

    #         for a1 in result.scalars():
    #             print(a1)
    #             print(f"created at: {a1.create_date}")
    #             for b1 in a1.bs:
    #                 print(b1)

    # await db.engine.dispose()


asyncio.run(async_main())
