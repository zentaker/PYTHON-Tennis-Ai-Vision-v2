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
from ..domain.errors import PlatformError

logger = logging.getLogger("tennisai.platform.http")

ERROR_DEFINITIONS: dict[str, tuple[int, str, str]] = {
    "INVALID_CURSOR": (400, "cursor is invalid", "The pagination cursor cannot be decoded."),
    "INVALID_REQUEST": (400, "request is invalid", "The request is syntactically invalid."),
    "SESSION_NOT_FOUND": (404, "session not found", "The requested session does not exist."),
    "VIDEO_NOT_FOUND": (404, "video not found", "The requested video does not exist in the session."),
    "STORAGE_OBJECT_MISSING": (404, "storage object is not present", "The uploaded object is missing from object storage."),
    "SOURCE_VIDEO_ALREADY_EXISTS": (409, "session already has a source video", "A source video has already been initiated for the session."),
    "INVALID_SESSION_STATE": (409, "session state does not allow this operation", "The session is not in a state that permits this operation."),
    "UPLOAD_METADATA_MISMATCH": (409, "upload metadata does not match initiation", "Completion metadata differs from the initiated upload."),
    "UPLOAD_SHA_MISMATCH": (409, "initiate and complete sha256 values differ", "The SHA-256 declarations do not match."),
    "STORAGE_OBJECT_MISMATCH": (409, "storage object does not match declared upload", "Object storage metadata differs from the declared upload."),
    "VIDEO_SIZE_EXCEEDED": (413, "video size exceeds configured limit", "The requested video exceeds the configured maximum size."),
    "VALIDATION_ERROR": (422, "request validation failed", "One or more request fields failed validation."),
    "INVALID_SHA256": (422, "sha256 must be 64 hexadecimal characters", "The SHA-256 value must contain exactly 64 hexadecimal characters."),
    "UNSUPPORTED_VIDEO_CONTENT_TYPE": (422, "unsupported video content type", "The video content type is not supported."),
    "VIDEO_EXTENSION_MISMATCH": (422, "filename extension does not match content type", "The filename extension does not match the content type."),
    "STORAGE_SIGNING_FAILED": (503, "storage could not sign the requested URL", "Object storage could not create a presigned URL."),
}


def error_response(code: str) -> dict:
    """Build a reusable OpenAPI response for one documented domain error."""
    status_code, message, description = ERROR_DEFINITIONS[code]
    return {
        "status_code": status_code,
        "model": ErrorResponse,
        "description": f"{code}: {description}",
        "content": {
            "application/json": {
                "examples": {
                    code: {
                        "summary": code,
                        "value": {
                            "error": {
                                "code": code,
                                "message": message,
                                "details": {},
                                "request_id": "2f9e4f25-9d45-4e04-a5e7-8dd3b6c2d310",
                            }
                        },
                    }
                }
            }
        },
    }


def error_responses(*codes: str) -> dict[int, dict]:
    """Return status-keyed responses while preserving each code as an example."""
    grouped: dict[int, dict] = {}
    for code in codes:
        response = error_response(code)
        status_code = response.pop("status_code")
        existing = grouped.get(status_code)
        if existing is None:
            grouped[status_code] = response
            continue
        existing["description"] += f"; {response['description']}"
        examples = response["content"]["application/json"]["examples"]
        existing["content"]["application/json"]["examples"].update(examples)
    return grouped


def not_found(message: str = "not found") -> PlatformError:
    return PlatformError(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", message)


def invalid(message: str) -> PlatformError:
    return PlatformError(status.HTTP_400_BAD_REQUEST, "INVALID_REQUEST", message)


async def platform_error_handler(request: Request, exc: PlatformError) -> JSONResponse:
    return _error_response(request, exc.status_code, exc.code, exc.message, exc.details)


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
    code = "VALIDATION_ERROR"
    if any("sha256" in {str(part) for part in error.get("loc", ())} for error in exc.errors()):
        code = "INVALID_SHA256"
    elif any("content_type" in {str(part) for part in error.get("loc", ())} for error in exc.errors()):
        code = "UNSUPPORTED_VIDEO_CONTENT_TYPE"
    return _error_response(
        request,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        code,
        ERROR_DEFINITIONS[code][1],
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
    request_id = incoming if incoming and len(incoming) <= 128 and incoming.isprintable() else str(uuid4())
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
