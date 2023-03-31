import logging
import re
import secrets
import typing as t

import click
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.orm.exc
from quart import current_app
from quart import g
from quart import Quart
from quart import request
from quart import Request
from quart.cli import AppGroup
from quart.cli import pass_script_info
from quart.cli import ScriptInfo
from quart_schema.extension import QUART_SCHEMA_SECURITY_ATTRIBUTE
from quart_schema.extension import security_scheme
from quart_schema.openapi import APIKeySecurityScheme
from quart_schema.openapi import HttpSecurityScheme
from quart_schema.openapi import SecuritySchemeBase
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden

from .model import AuthUser
from .model import MagicClient
from .schema import BaseSchema
from .util import ObjectID


sa = sqlalchemy

cli = AppGroup("auth")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def authorized_request(security_schemes: t.Sequence[t.Dict[str, t.List[t.Any]]]):
    def decorator(func):
        return security_scheme(security_schemes)(func)

    return decorator


class MyRequest(Request):
    @property
    def ip_addr(self):
        return self.remote_addr

    @property
    def locale(self):
        return self.accept_languages.best_match(["en"]) or "en"

    @property
    def redirect_url(self):
        return self.args.get("redirect_url") or self.headers.get("x-redirect-url")


class ValidatorError(RuntimeError):
    pass


class SubjectNotFound(ValidatorError):
    pass


class CredentialNotFound(ValidatorError):
    pass


class Credential(BaseSchema):
    scheme: SecuritySchemeBase
    value: t.Optional[str] = None
    subject: t.Union[MagicClient, AuthUser]


class AuthenticationValidator:
    name: str
    scheme: SecuritySchemeBase

    def extract(self, request: Request) -> str:
        ...

    def lookup(self, value: str, session: Session) -> t.Any:
        ...

    def authenticate(self, request: Request) -> Credential:
        ...


class PublicAPIKeyValidator(AuthenticationValidator):
    name = "public-api-key"
    scheme = APIKeySecurityScheme(in_="header", name="X-Public-API-Key")

    def extract(self, request: Request) -> str:
        if self.scheme.in_ == "header":
            return request.headers.get(self.scheme.name, None)
        elif self.scheme.in_ == "cookie":
            return request.cookies.get(self.scheme.name, None)
        elif self.scheme.in_ == "query":
            return request.args.get(self.scheme.name, None)
        else:
            raise ValueError(f"No token found for {self.scheme}")

    def lookup(self, value: str, session: Session) -> t.Any:
        statement = sa.select(MagicClient).where(MagicClient.public_api_key == value).limit(1)

        try:
            result = session.scalars(statement).one()
        except sa.orm.exc.NoResultFound:
            raise SubjectNotFound(f"No MagicClient found for public_api_key {value}")

        return result

    def authenticate(self, request: Request, session: Session) -> Credential:
        value = self.extract(request)
        if value is None:
            raise CredentialNotFound()
        subject = self.lookup(value, session)
        return Credential(scheme=self.scheme, value=value, subject=subject)


class SessionTokenValidator(AuthenticationValidator):
    name = "session-token-bearer"
    scheme = HttpSecurityScheme(scheme="bearer", bearer_format="opaque")

    AUTHORIZATION_PATTERN = re.compile(r"Bearer (?P<token>.+)")

    def extract(self, request: Request) -> str:
        if self.scheme.scheme != "bearer":
            return

        value = request.headers.get("authorization")
        m = self.AUTHORIZATION_PATTERN.match(value)
        if m is None:
            raise ValueError("Bearer token failed validation")

        return m.group("token")

    def lookup(self, value: str, session: Session) -> t.Any:
        statement = sa.select(AuthUser).where(AuthUser.current_session_token == value).limit(1)

        try:
            result = session.scalars(statement).one()
        except sa.orm.exc.NoResultFound:
            raise SubjectNotFound(f"No AuthUser found for session_token {value}")

        return result

    def authenticate(self, request: Request, session: Session) -> Credential:
        value = self.extract(request)
        if value is None:
            raise CredentialNotFound()
        subject = self.lookup(value, session)
        return Credential(scheme=self.scheme, value=value, subject=subject)


class RequestAuthenticator:
    validators = [PublicAPIKeyValidator(), SessionTokenValidator()]
    validator_scheme_map = {v.name: v for v in validators}

    def enforce(self, security_schemes: t.Sequence[t.Dict[str, t.List[t.Any]]], session: Session):
        passed, failed = [], []
        for scheme_credential in self.validate_security(security_schemes, session):
            if all(scheme_credential.values()):
                passed.append(scheme_credential)
            else:
                failed.append(scheme_credential)
        if passed:
            return passed
        raise Forbidden()

    def validate_security(
        self, security_schemes: t.Sequence[t.Dict[str, t.List[t.Any]]], session: Session
    ):
        if not security_schemes:
            return

        for scheme in security_schemes:
            scheme_credentials = {}
            for name, _ in scheme.items():
                validator = self.validator_scheme_map[name]
                credential = None
                try:
                    credential = validator.authenticate(request, session)
                except ValidatorError:
                    pass
                except:
                    logger.exception(f"Unknown error while validating {name}")
                    raise
                finally:
                    scheme_credentials[name] = credential
            yield scheme_credentials


# def convert_model_result(func: t.Callable) -> t.Callable:
#     @wraps(func)
#     async def decorator(result: ResponseReturnValue) -> Response:
#         status_or_headers = None
#         headers = None
#         if isinstance(result, tuple):
#             value, status_or_headers, headers = result + (None,) * (3 - len(result))
#         else:
#             value = result

#         was_model = False
#         if is_dataclass(value):
#             dict_or_value = asdict(value)
#             was_model = True
#         elif isinstance(value, BaseModel):
#             dict_or_value = value.dict(by_alias=True)
#             was_model = True
#         else:
#             dict_or_value = value

#         if was_model:
#             dict_or_value = camelize(dict_or_value)

#         return await func((dict_or_value, status_or_headers, headers))

#     return decorator


class QuartAuth:
    authenticator = RequestAuthenticator()

    def __init__(self, app: t.Optional[Quart] = None):
        if app is not None:
            self.init_app(app)

    def init_app(self, app: Quart):
        app.before_request(self.auth_endpoint_security)

        app.request_class = MyRequest

        self.security_schemes = app.config.get("QUART_AUTH_SECURITY_SCHEMES", {})
        app.cli.add_command(cli)

    def auth_endpoint_security(self):
        db = current_app.extensions.get("sqlalchemy")
        view_function = current_app.view_functions[request.endpoint]
        security_schemes = getattr(view_function, QUART_SCHEMA_SECURITY_ATTRIBUTE, None)
        if security_schemes is None:
            g.authorized_credentials = {}

        with db.bind.Session() as session:
            results = self.authenticator.enforce(security_schemes, session)
            authorized_credentials = {}
            for result in results:
                authorized_credentials.update(result)
            g.authorized_credentials = authorized_credentials


from .model import EntityType
from .model import MagicClient
from .model import Provenance


@cli.command("add-user")
@click.option(
    "--email",
    type=str,
    default="default@none.com",
    help="email",
)
@click.option(
    "--user-type",
    # type=click.Choice(list(EntityType.__members__)),
    type=click.Choice(["FORTMATIC", "MAGIC", "CONNECT"]),
    default="MAGIC",
    help="user type",
)
@click.option(
    "--client-id",
    type=int,
    required=True,
    help="client id",
)
@pass_script_info
def add_user(info: ScriptInfo, email: str, user_type: str, client_id: int) -> None:
    app = info.load_app()
    db = app.extensions.get("sqlalchemy")

    with db.bind.Session() as s:
        with s.begin():
            user = AuthUser(
                email=email,
                user_type=EntityType[user_type].value,
                client_id=ObjectID(client_id),
                provenance=Provenance.LINK,
                current_session_token=secrets.token_hex(16),
            )
            s.add(user)
            s.flush()
            s.refresh(user)

    click.echo(f"Created user {user.id} with session_token: {user.current_session_token}")


@cli.command("add-client")
@click.option(
    "--name",
    type=str,
    default="My App",
    help="app name",
)
@pass_script_info
def add_client(info: ScriptInfo, name: str) -> None:
    app = info.load_app()
    db = app.extensions.get("sqlalchemy")
    with db.bind.Session() as s:
        with s.begin():
            client = MagicClient(app_name=name, public_api_key=secrets.token_hex(16))
            s.add(client)
            s.flush()
            s.refresh(client)

    click.echo(f"Created client {client.id} with public_api_key: {client.public_api_key}")


auth = QuartAuth()
