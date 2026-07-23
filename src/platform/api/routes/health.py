from fastapi import APIRouter

router = APIRouter()


@router.get(
    "/healthz",
    tags=["Health"],
    operation_id="healthCheck",
    summary="Check service health",
    description="Return a process-level health response without probing external services.",
    responses={
        200: {
            "description": "Healthy",
            "content": {
                "application/json": {"example": {"status": "ok", "service": "session-platform"}}
            },
        }
    },
)
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "session-platform"}
