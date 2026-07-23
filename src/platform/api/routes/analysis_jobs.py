from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends

from ...schemas.analysis_job import (
    AnalysisRunCreate,
    AnalysisRunList,
    AnalysisRunResponse,
    CancelAnalysisRequest,
)
from ...services.analysis_jobs import (
    create_and_queue_run,
    get_analysis_run,
    list_analysis_runs,
    request_cancellation,
)
from ...domain.analysis_errors import ANALYSIS_ERROR_DEFINITIONS
from ...schemas.errors import ErrorResponse
from ..dependencies import db
from ..errors import error_responses


router = APIRouter(prefix="/api/v1")


def _analysis_error_responses(*codes: str) -> dict[int, dict]:
    grouped: dict[int, dict] = {}
    for code in codes:
        status_code, message = ANALYSIS_ERROR_DEFINITIONS[code]
        description = message
        response = grouped.setdefault(
            status_code,
            {
                "model": ErrorResponse,
                "description": description,
                "content": {"application/json": {"examples": {}}},
            },
        )
        response["content"]["application/json"]["examples"][code] = {
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
    return grouped


def _response(run) -> dict[str, Any]:
    return {
        "id": run.id,
        "session_id": run.session_id,
        "input_video_id": run.input_video_id,
        "status": run.status,
        "processing_profile": run.processing_profile,
        "idempotency_key": run.idempotency_key,
        "attempt": run.attempt,
        "max_attempts": run.max_attempts,
        "queued_at": run.queued_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "terminal_at": run.terminal_at,
        "worker_version": run.worker_version,
        "bundle_fingerprint": run.bundle_fingerprint,
        "result_manifest": run.result_manifest,
        "error_code": run.error_code,
        "error_message": run.error_message,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
        "cancel_requested_at": run.cancel_requested_at,
    }


@router.post(
    "/analysis-runs",
    response_model=AnalysisRunResponse,
    status_code=202,
    tags=["Analysis Jobs"],
    operation_id="requestAnalysisRun",
    summary="Request an analysis run",
    description="Idempotently enqueue a future analysis worker run for an uploaded session.",
    responses=_analysis_error_responses(
        "SESSION_NOT_READY_FOR_ANALYSIS", "ACTIVE_ANALYSIS_RUN_EXISTS", "IDEMPOTENCY_KEY_REUSED"
    ),
)
def request_run(
    payload: AnalysisRunCreate = Body(...), database=Depends(db)
):
    return _response(
        create_and_queue_run(
            database,
            payload.session_id,
            payload.processing_profile.value,
            payload.max_attempts,
            payload.idempotency_key,
        )
    )


@router.get(
    "/analysis-runs/{run_id}",
    response_model=AnalysisRunResponse,
    tags=["Analysis Jobs"],
    operation_id="getAnalysisRun",
    summary="Get an analysis run",
    description="Return persisted analysis run state without inventing progress.",
    responses=_analysis_error_responses("ANALYSIS_RUN_NOT_FOUND"),
)
def get_run(run_id: UUID, database=Depends(db)):
    return _response(get_analysis_run(database, run_id))


@router.get(
    "/sessions/{session_id}/analysis-runs",
    response_model=AnalysisRunList,
    tags=["Analysis Jobs"],
    operation_id="listSessionAnalysisRuns",
    summary="List session analysis runs",
    description="List all analysis runs associated with a session.",
    responses=error_responses("SESSION_NOT_FOUND"),
)
def list_runs(session_id: UUID, database=Depends(db)):
    return {"items": [_response(run) for run in list_analysis_runs(database, session_id)]}


@router.post(
    "/analysis-runs/{run_id}/cancel",
    response_model=AnalysisRunResponse,
    tags=["Analysis Jobs"],
    operation_id="cancelAnalysisRun",
    summary="Request analysis cancellation",
    description="Cancel a queued run or request cooperative cancellation from its worker.",
    responses=_analysis_error_responses("ANALYSIS_CANCELLATION_INVALID"),
)
def cancel_run(
    run_id: UUID,
    payload: CancelAnalysisRequest | None = Body(default=None),
    database=Depends(db),
):
    del payload
    return _response(request_cancellation(database, run_id))
