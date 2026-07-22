#!/usr/bin/env python3
"""Validate the OpenAPI and generated Postman contract as one source of truth."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts.export_session_api_postman import collection_from_openapi

ROOT = Path(__file__).parents[1]
OPENAPI = ROOT / "config/platform/session_api_v1.openapi.json"
COLLECTION = ROOT / "docs/postman/TennisAI-Session-API.postman_collection.json"
ENVIRONMENT = ROOT / "docs/postman/TennisAI-Local.postman_environment.json"
ROUTES = ROOT / "src/platform/api/routes"
SENSITIVE = re.compile(r"(?i)(aws[_-]?access|secret[_-]?key|password|credential|bearer|token)")


def _operations(openapi: dict) -> list[tuple[str, str, dict]]:
    return [
        (path, method.upper(), operation)
        for path, path_item in openapi["paths"].items()
        for method, operation in path_item.items()
        if method.lower() in {"get", "post", "put", "patch", "delete"}
    ]


def main() -> int:
    openapi = json.loads(OPENAPI.read_text(encoding="utf-8"))
    collection = json.loads(COLLECTION.read_text(encoding="utf-8"))
    environment = json.loads(ENVIRONMENT.read_text(encoding="utf-8"))
    operations = _operations(openapi)
    operation_ids = [operation["operationId"] for _, _, operation in operations]
    assert len(operation_ids) == len(set(operation_ids)), "operation IDs must be unique"
    assert all(path == "/healthz" or path.startswith("/api/v1/") for path, _, _ in operations)
    digest = hashlib.sha256(OPENAPI.read_bytes()).hexdigest()
    assert collection == collection_from_openapi(openapi, digest), "Postman is stale"
    collection_operations = [
        (item["_openapiPath"], item["_openapiMethod"])
        for folder in collection["item"]
        for item in folder["item"]
    ]
    assert sorted(collection_operations) == sorted((path, method) for path, method, _ in operations)
    environment_keys = [entry["key"] for entry in environment["values"]]
    assert environment_keys == ["baseUrl", "sessionId", "videoId", "analysisRunId"]
    assert not SENSITIVE.search(json.dumps(collection))
    assert not SENSITIVE.search(json.dumps(environment))
    for route in ROUTES.glob("*.py"):
        source = route.read_text(encoding="utf-8")
        assert "sqlalchemy" not in source, f"router imports SQLAlchemy: {route.name}"
        assert "boto3" not in source, f"router imports boto3: {route.name}"
        assert "select(" not in source, f"router executes SQL: {route.name}"
    print(json.dumps({"operations": len(operations), "openapi_sha256": digest, "status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
