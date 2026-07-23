#!/usr/bin/env python3
"""Validate the OpenAPI and generated Postman contract as one source of truth."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
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
    source = json.loads(
        (ROOT / "config/platform/SESSION_API_SOURCE.json").read_text(encoding="utf-8")
    )
    source_commit = source.get("source_commit", "")
    assert re.fullmatch(r"[0-9a-f]{40}", source_commit)
    assert source.get("source_commit_is_ancestor_of_head") is True
    assert (
        subprocess.run(
            ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"], check=False
        ).returncode
        == 0
    )
    assert (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source_commit, "HEAD"], check=False
        ).returncode
        == 0
    )
    assert source.get("sha256") == digest
    assert collection == collection_from_openapi(openapi, digest), "Postman is stale"
    collection_operations = [
        (item["_openapiPath"], item["_openapiMethod"])
        for folder in collection["item"]
        for item in folder["item"]
        if "_openapiPath" in item
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
    workflow_items = [
        item
        for folder in collection["item"]
        for item in folder["item"]
        if item.get("_generatedWorkflow") == "presignedUpload"
    ]
    assert len(workflow_items) == 1
    upload_request = workflow_items[0]["request"]
    assert upload_request["method"] == "PUT"
    assert upload_request["url"]["raw"] == "{{uploadUrl}}"
    assert upload_request["body"]["mode"] == "file"
    assert upload_request["body"]["file"]["src"] == ""
    assert [entry["key"] for entry in collection["variable"]] == [
        "baseUrl", "sessionId", "videoId", "analysisRunId",
        "uploadUrl", "uploadContentType", "uploadSizeBytes", "uploadSha256",
    ]
    assert all(entry["value"] == "" for entry in collection["variable"])
    initiate_items = [
        item
        for folder in collection["item"]
        for item in folder["item"]
        if item.get("_operationId") == "initiateVideoUpload"
    ]
    assert len(initiate_items) == 1
    initiate_script = json.dumps(initiate_items[0].get("event", []))
    assert "pm.environment.set('videoId'" in initiate_script
    assert "pm.collectionVariables.set('uploadUrl'" in initiate_script
    assert "pm.environment.set('uploadUrl'" not in initiate_script
    complete_items = [
        item
        for folder in collection["item"]
        for item in folder["item"]
        if item.get("_operationId") == "completeVideoUpload"
    ]
    assert len(complete_items) == 1
    complete_script = json.dumps(complete_items[0].get("event", []))
    for variable in ("uploadSizeBytes", "uploadContentType", "uploadSha256"):
        assert f"pm.collectionVariables.get('{variable}')" in complete_script
        assert f"pm.collectionVariables.unset('{variable}')" in complete_script
    assert "pm.collectionVariables.unset('uploadUrl')" in complete_script
    assert "pm.environment.set('uploadUrl'" not in json.dumps(collection)
    assert '"value": "{{uploadUrl}}"' not in json.dumps(environment)
    print(json.dumps({"operations": len(operations), "openapi_sha256": digest, "status": "ok"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
