from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.platform.api.analysis_app import create_analysis_app
from src.platform.config.settings import PlatformSettings
from src.platform.db.base import Base
from src.platform.db.models import SessionRecord, Video


def _app_with_uploaded_session() -> tuple[FastAPI, SessionRecord]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        session = SessionRecord(
            title="HTTP contract",
            status="UPLOADED",
            processing_profile="STANDARD",
            surface="unknown",
        )
        db.add(session)
        db.flush()
        video = Video(
            session_id=session.id,
            role="SOURCE",
            display_name="contract.mp4",
            object_key=f"sessions/{session.id}/source/video",
            content_type="video/mp4",
            size_bytes=1,
            sha256="0" * 64,
            integrity_status="STORAGE_VERIFIED",
        )
        db.add(video)
        db.flush()
        session.source_video_id = video.id
        db.commit()
        db.refresh(session)
        session_id = session.id
    app = create_analysis_app(PlatformSettings(database_url="sqlite://"), db_factory=factory)
    detached = SessionRecord(id=session_id, status="UPLOADED")
    return app, detached


def _invoke(app: FastAPI, method: str, path: str, payload: dict | None = None) -> dict:
    body = json.dumps(payload).encode() if payload is not None else b""
    messages = iter([{"type": "http.request", "body": body, "more_body": False}])
    response = {"status": None, "body": b""}

    async def receive():
        return next(messages)

    async def send(message):
        if message["type"] == "http.response.start":
            response["status"] = message["status"]
        elif message["type"] == "http.response.body":
            response["body"] += message.get("body", b"")

    async def run():
        await app(
            {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [(b"content-type", b"application/json"), (b"host", b"test")],
                "client": ("test", 1),
                "server": ("test", 80),
                "root_path": "",
            },
            receive,
            send,
        )

    asyncio.run(run())
    return {"status": response["status"], "body": json.loads(response["body"] or b"{}")}


def test_analysis_openapi_is_additive_and_stable():
    app, _ = _app_with_uploaded_session()
    document = app.openapi()
    assert document["openapi"].startswith("3.")
    assert set(document["paths"]) == {
        "/api/v1/analysis-runs",
        "/api/v1/analysis-runs/{run_id}",
        "/api/v1/analysis-runs/{run_id}/cancel",
        "/api/v1/sessions/{session_id}/analysis-runs",
    }
    operation_ids = [
        operation["operationId"]
        for path in document["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_analysis_http_request_and_idempotency():
    app, session = _app_with_uploaded_session()
    payload = {"session_id": str(session.id), "processing_profile": "STANDARD"}
    first = _invoke(app, "POST", "/api/v1/analysis-runs", payload)
    second = _invoke(app, "POST", "/api/v1/analysis-runs", payload)
    assert first["status"] == second["status"] == 202
    assert first["body"]["id"] == second["body"]["id"]
    run_id = first["body"]["id"]
    fetched = _invoke(app, "GET", f"/api/v1/analysis-runs/{run_id}")
    assert fetched["status"] == 200 and fetched["body"]["status"] == "QUEUED"
    missing = _invoke(app, "GET", f"/api/v1/analysis-runs/{uuid4()}")
    assert missing["status"] == 404
    assert missing["body"]["error"]["request_id"]
