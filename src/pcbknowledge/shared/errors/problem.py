"""RFC 7807 / RFC 9457 problem-details handling for the HTTP boundary."""

import logging
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

_RESERVED_MEMBERS = {"type", "title", "status", "detail", "instance"}


class ProblemDetail(BaseModel):
    """Stable base shape for API failures; extension members are permitted."""

    model_config = ConfigDict(extra="allow")

    type: str = "about:blank"
    title: str
    status: int = Field(ge=400, le=599)
    detail: str | None = None
    instance: str | None = None


class ProblemException(Exception):
    """An expected HTTP failure represented as problem details."""

    def __init__(
        self,
        *,
        status: int,
        title: str,
        detail: str,
        type_uri: str = "about:blank",
        extensions: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        if status < 400 or status > 599:
            raise ValueError("problem status must be an HTTP error status")
        supplied_extensions = dict(extensions or {})
        collisions = _RESERVED_MEMBERS.intersection(supplied_extensions)
        if collisions:
            joined = ", ".join(sorted(collisions))
            raise ValueError(f"problem extensions use reserved members: {joined}")
        self.status = status
        self.title = title
        self.detail = detail
        self.type_uri = type_uri
        self.extensions = supplied_extensions
        self.headers = _validated_headers(headers)


def _validated_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    validated: dict[str, str] = {}
    for name, value in (headers or {}).items():
        if not name or "\r" in name or "\n" in name or "\r" in value or "\n" in value:
            raise ValueError("problem response headers are invalid")
        validated[name] = value
    return validated


def _response(
    request: Request,
    *,
    status: int,
    title: str,
    detail: str | None,
    type_uri: str = "about:blank",
    extensions: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    problem = ProblemDetail(
        type=type_uri,
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
    )
    payload = problem.model_dump(mode="json", exclude_none=True)
    payload.update(extensions or {})
    response_headers = {"Cache-Control": "no-store"}
    response_headers.update(_validated_headers(headers))
    return JSONResponse(
        status_code=status,
        content=payload,
        media_type="application/problem+json",
        headers=response_headers,
    )


async def _problem_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ProblemException)
    return _response(
        request,
        status=exc.status,
        title=exc.title,
        detail=exc.detail,
        type_uri=exc.type_uri,
        extensions=exc.extensions,
        headers=exc.headers,
    )


async def _http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    detail = exc.detail if isinstance(exc.detail, str) else "The request could not be completed."
    return _response(
        request,
        status=exc.status_code,
        title="HTTP request failed",
        detail=detail,
        headers=exc.headers,
    )


async def _validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    errors = [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "code": error["type"],
        }
        for error in exc.errors()
    ]
    return _response(
        request,
        status=422,
        title="Request validation failed",
        detail="One or more request fields are invalid.",
        type_uri="urn:pcbknowledge:problem:request-validation",
        extensions={"errors": errors},
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API exception",
        extra={
            "request_path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    return _response(
        request,
        status=500,
        title="Internal server error",
        detail="The server could not complete the request.",
    )


def install_problem_handlers(app: FastAPI) -> None:
    """Install one fail-closed problem-details boundary for the application."""

    app.add_exception_handler(ProblemException, _problem_exception_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
