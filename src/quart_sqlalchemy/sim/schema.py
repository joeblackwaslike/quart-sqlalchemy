import typing as t
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import validator

from .util import ObjectID


class BaseSchema(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectID: lambda v: v.encode(),
            datetime: lambda dt: int(dt.timestamp()),
        }

    @classmethod
    def _get_value(cls, v: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if hasattr(v, "__serialize__"):
            return v.__serialize__()
        for type_, converter in cls.__config__.json_encoders.items():
            if isinstance(v, type_):
                return converter(v)

        return super()._get_value(v, *args, **kwargs)


class ResponseWrapper(BaseSchema):
    """Generic response wrapper"""

    error_code: str = ""
    status: str = ""
    message: str = ""
    data: t.Any = Field(default_factory=dict)

    @validator("status")
    def set_status_by_error_code(cls, v, values):
        error_code = values.get("error_code")
        if error_code:
            return "failed"
        return "ok"
