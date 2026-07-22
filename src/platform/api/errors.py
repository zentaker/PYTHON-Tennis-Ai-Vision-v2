from __future__ import annotations

import json
import logging
import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from ..schemas.errors import ErrorResponse

logger = logging.getLogger("tennisai.platform.http")

ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Internal server error"},
}


def not_found(message: str = "not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def invalid(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", str(uuid4()))


def _error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
                "request_id": _request_id(request),
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    code = {
        400: "INVALID_REQUEST",
        404: "RESOURCE_NOT_FOUND",
    }.get(exc.status_code, f"HTTP_{exc.status_code}")
    detail = exc.detail if isinstance(exc.detail, str) else "request failed"
    details = exc.detail if isinstance(exc.detail, dict) else {}
    return _error_response(request, exc.status_code, code, detail, details)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "VALIDATION_ERROR",
        "request validation failed",
        {"errors": exc.errors()},
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        json.dumps(
            {
                "event": "unhandled_exception",
                "request_id": _request_id(request),
                "exception_type": type(exc).__name__,
            },
            sort_keys=True,
        )
    )
    return _error_response(
        request,
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "INTERNAL_SERVER_ERROR",
        "internal server error",
    )


async def request_logging_middleware(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming if len(incoming) <= 128 and incoming.isprintable() else str(uuid4())
    request.state.request_id = request_id
    started = time.perf_counter()
    response = None
    try:
        response = await call_next(request)
        return response
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code if response is not None else 500,
                    "duration_ms": duration_ms,
                },
                sort_keys=True,
            )
        )
        if response is not None:
            response.headers["X-Request-ID"] = request_id
