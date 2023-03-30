# import inspect
# import typing as t
# from dataclasses import asdict
# from dataclasses import is_dataclass
from functools import wraps

# from pydantic import BaseModel
# from pydantic import ValidationError
# from pydantic.dataclasses import dataclass as pydantic_dataclass
# from pydantic.schema import model_schema
from quart import current_app
from quart import g


# from quart import request
# from quart import ResponseReturnValue as QuartResponseReturnValue
# from quart_schema.typing import Model
# from quart_schema.typing import PydanticModel
# from quart_schema.typing import ResponseReturnValue
# from quart_schema.validation import _convert_headers
# from quart_schema.validation import DataSource
# from quart_schema.validation import QUART_SCHEMA_RESPONSE_ATTRIBUTE
# from quart_schema.validation import ResponseHeadersValidationError
# from quart_schema.validation import ResponseSchemaValidationError
# from quart_schema.validation import validate_headers
# from quart_schema.validation import validate_querystring
# from quart_schema.validation import validate_request


def authorized_request(authenticate_client: bool = False, authenticate_user: bool = False):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if authenticate_client:
                if not g.auth.client:
                    raise RuntimeError("Unable to authenticate client")
                kwargs.update(client_id=g.auth.client.id)

            if authenticate_user:
                if not g.auth.user:
                    raise RuntimeError("Unable to authenticate user")
                kwargs.update(user_id=g.auth.user.id)

            return await current_app.ensure_async(func)(*args, **kwargs)

        return wrapper

    return decorator


# def validate_response() -> t.Callable:
#     def decorator(
#         func: t.Callable[..., ResponseReturnValue]
#     ) -> t.Callable[..., QuartResponseReturnValue]:
#         undecorated = func
#         while hasattr(undecorated, "__wrapped__"):
#             undecorated = undecorated.__wrapped__

#         signature = inspect.signature(undecorated)
#         derived_schema = signature.return_annotation or dict

#         schemas = getattr(func, QUART_SCHEMA_RESPONSE_ATTRIBUTE, {})
#         schemas[200] = (derived_schema, None)
#         setattr(func, QUART_SCHEMA_RESPONSE_ATTRIBUTE, schemas)

#         @wraps(func)
#         async def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
#             result = await current_app.ensure_async(func)(*args, **kwargs)

#             status_or_headers = None
#             headers = None
#             if isinstance(result, tuple):
#                 value, status_or_headers, headers = result + (None,) * (3 - len(result))
#             else:
#                 value = result

#             status = 200
#             if isinstance(status_or_headers, int):
#                 status = int(status_or_headers)

#             schemas = getattr(func, QUART_SCHEMA_RESPONSE_ATTRIBUTE, {200: dict})
#             model_class = schemas.get(status, dict)

#             try:
#                 if isinstance(value, dict):
#                     model_value = model_class(**value)
#                 elif type(value) == model_class:
#                     model_value = value
#                 elif is_dataclass(value):
#                     model_value = model_class(**asdict(value))
#                 else:
#                     return result, status, headers

#             except ValidationError as error:
#                 raise ResponseHeadersValidationError(error)

#             headers_value = headers
#             return model_value, status, headers_value

#         return wrapper

#     return decorator


# def validate(
#     *,
#     querystring: t.Optional[Model] = None,
#     request: t.Optional[Model] = None,
#     request_source: DataSource = DataSource.JSON,
#     headers: t.Optional[Model] = None,
#     responses: t.Dict[int, t.Tuple[Model, t.Optional[Model]]],
# ) -> t.Callable:
#     """Validate the route.

#     This is a shorthand combination of of the validate_querystring,
#     validate_request, validate_headers, and validate_response
#     decorators. Please see the docstrings for those decorators.
#     """

#     def decorator(func: t.Callable) -> t.Callable:
#         if querystring is not None:
#             func = validate_querystring(querystring)(func)
#         if request is not None:
#             func = validate_request(request, source=request_source)(func)
#         if headers is not None:
#             func = validate_headers(headers)(func)
#         for status, models in responses.items():
#             func = validate_response(models[0], status, models[1])
#         return func

#     return decorator
