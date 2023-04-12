import typing as t
from dataclasses import asdict
from dataclasses import is_dataclass
from functools import wraps

from humps import camelize
from humps import decamelize
from pydantic import BaseModel
from pydantic import ValidationError
from quart import current_app
from quart import request
from quart import Response
from quart_schema.typing import Model
from quart_schema.typing import ResponseReturnValue
from quart_schema.validation import QUART_SCHEMA_REQUEST_ATTRIBUTE
from quart_schema.validation import QUART_SCHEMA_RESPONSE_ATTRIBUTE
from quart_schema.validation import RequestSchemaValidationError
from quart_schema.validation import ResponseSchemaValidationError


def convert_model_result(func: t.Callable) -> t.Callable:
    @wraps(func)
    async def decorator(result: ResponseReturnValue) -> Response:
        status_or_headers = None
        headers = None
        if isinstance(result, tuple):
            value, status_or_headers, headers = result + (None,) * (3 - len(result))
        else:
            value = result

        was_model = False
        if is_dataclass(value):
            dict_or_value = asdict(value)
            was_model = True
        elif isinstance(value, BaseModel):
            dict_or_value = value.dict(by_alias=True)
            was_model = True
        else:
            dict_or_value = value

        if was_model:
            dict_or_value = camelize(dict_or_value)

        return await func((dict_or_value, status_or_headers, headers))

    return decorator


def validate_request(model_class: Model) -> t.Callable:
    def decorator(func: t.Callable) -> t.Callable:
        setattr(func, QUART_SCHEMA_REQUEST_ATTRIBUTE, (model_class, None))

        @wraps(func)
        async def wrapper(*args, **kwargs):
            data = await request.get_json()
            data = decamelize(data)

            try:
                model = model_class(**data)
            except (TypeError, ValidationError) as error:
                raise RequestSchemaValidationError(error)
            else:
                return await current_app.ensure_async(func)(*args, data=model, **kwargs)

        return wrapper

    return decorator


def validate_response(model_class: Model, status_code: int = 200) -> t.Callable:
    def decorator(func):
        schemas = getattr(func, QUART_SCHEMA_RESPONSE_ATTRIBUTE, {})
        schemas[status_code] = (model_class, None)
        setattr(func, QUART_SCHEMA_RESPONSE_ATTRIBUTE, schemas)

        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await current_app.ensure_async(func)(*args, **kwargs)

            status_or_headers = None
            headers = None
            if isinstance(result, tuple):
                value, status_or_headers, headers = result + (None,) * (3 - len(result))
            else:
                value = result

            status = 200
            if isinstance(status_or_headers, int):
                status = int(status_or_headers)

            if status == status_code:
                try:
                    if isinstance(value, dict):
                        model_value = model_class(**value)
                    elif type(value) == model_class:
                        model_value = value
                    else:
                        raise ResponseSchemaValidationError()
                except ValidationError as error:
                    raise ResponseSchemaValidationError(error)

                return model_value, status, headers
            else:
                return result

        return wrapper

    return decorator


def inject_request(key: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            kwargs[key] = request._get_current_object()
            return await current_app.ensure_async(func)(*args, **kwargs)

        return wrapper

    return decorator
