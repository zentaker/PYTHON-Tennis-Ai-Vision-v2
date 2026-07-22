#!/usr/bin/env python3
"""Generate the Postman collection from the canonical Session API OpenAPI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
OPENAPI_PATH = ROOT / "config/platform/session_api_v1.openapi.json"
COLLECTION_PATH = ROOT / "docs/postman/TennisAI-Session-API.postman_collection.json"


def _example_from_schema(schema: dict[str, Any]) -> Any:
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    if schema.get("type") == "object":
        return {
            name: _example_from_schema(value)
            for name, value in schema.get("properties", {}).items()
            if name in schema.get("required", [])
        }
    if schema.get("type") == "array":
        return []
    return {"string": "", "integer": 0, "number": 0, "boolean": False}.get(schema.get("type"), "")


def _body(operation: dict[str, Any]) -> dict[str, Any] | None:
    content = operation.get("requestBody", {}).get("content", {}).get("application/json")
    if not content:
        return None
    examples = content.get("examples", {})
    if examples:
        value = next(iter(examples.values())).get("value", {})
    else:
        value = _example_from_schema(content.get("schema", {}))
    return {
        "mode": "raw",
        "raw": json.dumps(value, indent=2, sort_keys=True),
        "options": {"raw": {"language": "json"}},
    }


def _postman_path(path: str) -> str:
    replacements = {
        "{session_id}": "{{sessionId}}",
        "{video_id}": "{{videoId}}",
        "{analysis_run_id}": "{{analysisRunId}}",
    }
    for source, target in replacements.items():
        path = path.replace(source, target)
    return path


def _item(path: str, method: str, operation: dict[str, Any]) -> dict:
    rendered_path = _postman_path(path)
    query = []
    for parameter in operation.get("parameters", []):
        if parameter.get("in") == "query":
            query.append({"key": parameter["name"], "value": "", "disabled": True})
    request = {
        "method": method.upper(),
        "header": (
            [{"key": "Content-Type", "value": "application/json"}] if _body(operation) else []
        ),
        "url": {
            "raw": "{{baseUrl}}" + rendered_path,
            "host": ["{{baseUrl}}"],
            "path": rendered_path.lstrip("/").split("/"),
        },
        "description": operation.get("description") or operation.get("summary", ""),
    }
    if query:
        request["url"]["query"] = query
    body = _body(operation)
    if body:
        request["body"] = body
    return {
        "name": operation.get("summary") or operation["operationId"],
        "request": request,
        "response": [],
        "protocolProfileBehavior": {},
        "_operationId": operation["operationId"],
        "_openapiPath": path,
        "_openapiMethod": method.upper(),
    }


def collection_from_openapi(openapi: dict[str, Any], digest: str) -> dict[str, Any]:
    folders: dict[str, list[dict]] = {}
    for path in sorted(openapi.get("paths", {})):
        for method, operation in sorted(openapi["paths"][path].items()):
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = (operation.get("tags") or ["Session API"])[0]
            folders.setdefault(tag, []).append(_item(path, method, operation))
    items = [{"name": tag, "item": folders[tag]} for tag in sorted(folders)]
    return {
        "info": {
            "name": "TennisAI Session API",
            "description": "Generated from config/platform/session_api_v1.openapi.json.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "variable": [
            {"key": "baseUrl", "value": "{{baseUrl}}"},
            {"key": "sessionId", "value": "{{sessionId}}"},
            {"key": "videoId", "value": "{{videoId}}"},
            {"key": "analysisRunId", "value": "{{analysisRunId}}"},
        ],
        "item": items,
        "x-openapi-sha256": digest,
    }


def main() -> int:
    payload = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    digest = hashlib.sha256(OPENAPI_PATH.read_bytes()).hexdigest()
    collection = collection_from_openapi(payload, digest)
    COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    COLLECTION_PATH.write_text(
        json.dumps(collection, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {"path": str(COLLECTION_PATH.relative_to(ROOT)), "openapi_sha256": digest},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
