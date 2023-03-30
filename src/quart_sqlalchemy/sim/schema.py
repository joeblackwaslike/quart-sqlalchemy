from datetime import datetime

from pydantic import BaseModel

from quart_sqlalchemy.sim.util import ObjectID


class BaseSchema(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectID: lambda v: v.encode(),
            datetime: lambda dt: int(dt.timestamp()),
        }
