from __future__ import annotations

import re
from pathlib import PurePosixPath
from uuid import UUID

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    value = name.strip().replace("\\", "")
    if not value or value in {".", ".."}:
        raise ValueError("filename must not be empty")
    value = _SAFE_NAME.sub("_", value).strip("._")
    if not value:
        raise ValueError("filename must contain safe characters")
    return value


def validate_object_key(key: str, prefix: str | None = None) -> str:
    if not key or key.startswith("/") or "\\" in key or ".." in key:
        raise ValueError("unsafe object key")
    path = PurePosixPath(key)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("unsafe object key")
    normalized = str(path)
    if prefix is not None and (
        normalized != prefix.rstrip("/") and not normalized.startswith(prefix.rstrip("/") + "/")
    ):
        raise ValueError("object key escapes assigned prefix")
    return normalized


def source_video_key(session_id: UUID, video_id: UUID, filename: str) -> str:
    return validate_object_key(f"sessions/{session_id}/source/{video_id}/{safe_filename(filename)}")


def bundle_artifact_key(run_id: UUID, relative_path: str) -> str:
    return validate_object_key(f"runs/{run_id}/bundle/{relative_path}", f"runs/{run_id}/bundle")
