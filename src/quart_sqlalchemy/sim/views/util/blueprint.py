import inspect
import typing as t

from quart import Blueprint
from quart import Request
from quart_schema.validation import validate_headers
from quart_schema.validation import validate_querystring

from ...schema import BaseSchema
from .decorator import inject_request
from .decorator import validate_request
from .decorator import validate_response


class APIBlueprint(Blueprint):
    def _endpoint(
        self,
        uri: str,
        methods: t.Optional[t.Sequence[str]] = ("GET",),
        authorizer: t.Optional[t.Callable] = None,
        **route_kwargs,
    ):
        def decorator(func):
            sig = inspect.signature(func)

            param_annotation_map = {
                name: param.annotation for name, param in sig.parameters.items()
            }
            has_request_schema = "data" in sig.parameters and issubclass(
                param_annotation_map["data"],
                BaseSchema,
            )
            has_query_schema = "query_args" in sig.parameters and issubclass(
                param_annotation_map["query_args"],
                BaseSchema,
            )
            has_headers_schema = "headers" in sig.parameters and issubclass(
                param_annotation_map["headers"],
                BaseSchema,
            )

            has_response_schema = isinstance(sig.return_annotation, BaseSchema)

            should_inject_request, request_param_name = False, None
            for name in param_annotation_map:
                if isinstance(param_annotation_map[name], Request):
                    should_inject_request, request_param_name = True, name
                    break

            decorated = func

            if should_inject_request:
                decorated = inject_request(request_param_name)(decorated)

            if has_query_schema:
                decorated = validate_querystring(param_annotation_map["query_args"])(decorated)

            if has_headers_schema:
                decorated = validate_headers(param_annotation_map["headers"])(decorated)

            if has_request_schema:
                decorated = validate_request(param_annotation_map["data"])(decorated)

            if has_response_schema:
                decorated = validate_response(sig.return_annotation)(decorated)

            if authorizer:
                decorated = authorizer(decorated)

            return self.route(uri, t.cast(t.List[str], methods), **route_kwargs)(decorated)

        return decorator

    def get(self, *args, **kwargs):
        if "methods" in kwargs:
            del kwargs["methods"]

        return self._endpoint(*args, methods=["GET"], **kwargs)

    def post(self, *args, **kwargs):
        if "methods" in kwargs:
            del kwargs["methods"]

        return self._endpoint(*args, methods=["POST"], **kwargs)

    def put(self, *args, **kwargs):
        if "methods" in kwargs:
            del kwargs["methods"]

        return self._endpoint(*args, methods=["PUT"], **kwargs)

    def patch(self, *args, **kwargs):
        if "methods" in kwargs:
            del kwargs["methods"]

        return self._endpoint(*args, methods=["PATCH"], **kwargs)

    def delete(self, *args, **kwargs):
        if "methods" in kwargs:
            del kwargs["methods"]

        return self._endpoint(*args, methods=["DELETE"], **kwargs)
