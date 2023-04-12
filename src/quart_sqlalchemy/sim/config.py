import typing as t

import sqlalchemy
from pydantic import BaseSettings
from pydantic import Field
from pydantic import PyObject
from quart_schema import APIKeySecurityScheme
from quart_schema import HttpSecurityScheme
from quart_schema.openapi import SecuritySchemeBase

from quart_sqlalchemy import AsyncBindConfig
from quart_sqlalchemy import BindConfig
from quart_sqlalchemy.sim.db import MyBase


sa = sqlalchemy




class AppSettings(BaseSettings):

    class Config:
        env_file = ".env", ".secrets.env"

    LOAD_BLUEPRINTS: t.List[str] = Field(
        default_factory=lambda: ["quart_sqlalchemy.sim.views.api"]
    )
    LOAD_EXTENSIONS: t.List[str] = Field(
        default_factory=lambda: [
            "quart_sqlalchemy.sim.db.db",
            "quart_sqlalchemy.sim.app.schema",
            "quart_sqlalchemy.sim.auth.auth",
        ]
    )
    SECURITY_SCHEMES: t.Dict[str, SecuritySchemeBase] = Field(
        default_factory=lambda: {
            "public-api-key": APIKeySecurityScheme(in_="header", name="X-Public-API-Key"),
            "session-token-bearer": HttpSecurityScheme(scheme="bearer", bearer_format="opaque"),
        }
    )

    SQLALCHEMY_BINDS: t.Dict[str, t.Union[AsyncBindConfig, BindConfig]] = Field(
        default_factory=lambda: dict(default=BindConfig(engine=dict(url="sqlite:///app.db")))
    )
    SQLALCHEMY_BASE_CLASS: t.Type[t.Any] = Field(default=MyBase)

    WEB3_DEFAULT_CHAIN: str = Field(default="ethereum")
    WEB3_DEFAULT_NETWORK: str = Field(default="goerli")

    WEB3_PROVIDER_CLASS: PyObject = Field("web3.providers.HTTPProvider", env="WEB3_PROVIDER_CLASS")
    ALCHEMY_API_KEY: str = Field(env="ALCHEMY_API_KEY")
    WEB3_HTTPS_PROVIDER_URI: str = Field(env="WEB3_HTTPS_PROVIDER_URI")



settings = AppSettings()
