import typing as t
from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import Field
from pydantic import validator
from pydantic.generics import GenericModel

from .model import ConnectInteropStatus
from .model import EntityType
from .model import Provenance
from .model import WalletManagementType
from .model import WalletType
from .util import ObjectID


DataT = t.TypeVar("DataT")

json_encoders = {
    ObjectID: lambda v: v.encode(),
    datetime: lambda dt: int(dt.timestamp()),
    Enum: lambda e: e.value,
}


class BaseSchema(BaseModel):
    class Config:
        arbitrary_types_allowed = True
        json_encoders = dict(json_encoders)
        orm_mode = True

    @classmethod
    def _get_value(cls, v: t.Any, *args: t.Any, **kwargs: t.Any) -> t.Any:
        if hasattr(v, "__serialize__"):
            return v.__serialize__()
        for type_, converter in cls.__config__.json_encoders.items():
            if isinstance(v, type_):
                return converter(v)

        return super()._get_value(v, *args, **kwargs)


class ResponseWrapper(GenericModel, t.Generic[DataT]):
    """Generic response wrapper"""

    class Config:
        arbitrary_types_allowed = True
        json_encoders = dict(json_encoders)

    error_code: str = ""
    status: str = ""
    message: str = ""
    data: DataT = Field(default_factory=dict)

    @validator("status")
    def set_status_by_error_code(cls, v, values):
        return "failed" if (error_code := values.get("error_code")) else "ok"


class MagicClientSchema(BaseSchema):
    id: ObjectID
    app_name: str
    rate_limit_tier: t.Optional[str] = None
    connect_interop: t.Optional[ConnectInteropStatus] = None
    is_signing_modal_enabled: bool
    global_audience_enabled: bool
    public_api_key: str
    secret_api_key: str


class AuthUserSchema(BaseSchema):
    id: ObjectID
    client_id: ObjectID
    email: str
    phone_number: t.Optional[str] = None
    user_type: EntityType = EntityType.MAGIC
    provenance: t.Optional[Provenance] = None
    date_verified: t.Optional[datetime] = None
    is_admin: bool = False
    linked_primary_auth_user_id: t.Optional[ObjectID] = None
    global_auth_user_id: t.Optional[ObjectID] = None
    delegated_user_id: t.Optional[str] = None
    delegated_identity_pool_id: t.Optional[str] = None
    current_session_token: t.Optional[str] = None


class AuthWalletSchema(BaseSchema):
    id: ObjectID
    auth_user_id: ObjectID
    wallet_type: WalletType
    management_type: WalletManagementType
    public_address: str
    encrypted_private_address: str
    network: str
    is_exported: bool
