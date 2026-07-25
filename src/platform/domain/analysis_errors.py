from __future__ import annotations

from .errors import PlatformError


ANALYSIS_ERROR_DEFINITIONS: dict[str, tuple[int, str]] = {
    "ANALYSIS_RUN_NOT_FOUND": (404, "analysis run not found"),
    "IDEMPOTENCY_KEY_REUSED": (409, "idempotency key was reused with a different request"),
    "SESSION_NOT_READY_FOR_ANALYSIS": (409, "session is not ready for analysis"),
    "ACTIVE_ANALYSIS_RUN_EXISTS": (409, "an active analysis run already exists"),
    "ANALYSIS_JOB_NOT_AVAILABLE": (409, "no analysis job is available"),
    "ANALYSIS_LEASE_INVALID": (409, "analysis lease is invalid"),
    "ANALYSIS_LEASE_EXPIRED": (409, "analysis lease has expired"),
    "WORKER_NOT_AUTHORIZED": (403, "worker is not authorized"),
    "ANALYSIS_INVALID_TRANSITION": (409, "analysis run transition is not allowed"),
    "ANALYSIS_CANCELLATION_INVALID": (409, "analysis cancellation is not allowed"),
    "MAX_ATTEMPTS_EXCEEDED": (409, "analysis attempt limit has been exhausted"),
    "ARTIFACT_METADATA_INVALID": (422, "artifact metadata is invalid"),
    "ANALYSIS_FINALIZATION_CONFLICT": (409, "analysis run finalization conflicts with its state"),
}


def analysis_error(code: str, details: dict | None = None) -> PlatformError:
    status, message = ANALYSIS_ERROR_DEFINITIONS[code]
    return PlatformError(status, code, message, details or {})
