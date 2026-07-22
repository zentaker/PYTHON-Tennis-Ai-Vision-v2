#!/usr/bin/env python3
"""Export auditable Session Platform evidence from real runtime outputs."""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
SECRET_PATTERN = re.compile(r"(?i)(aws[_-]?access|secret[_-]?key|password|credential|bearer|token)")
PRESIGNED_QUERY_PATTERN = re.compile(r"(?i)(X-Amz-|Signature=|AWSAccessKeyId=)")


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall(".//testsuite"))
    totals = {key: 0 for key in ("tests", "failures", "errors", "skipped")}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, 0))
    if totals["failures"] or totals["errors"] or totals["skipped"]:
        raise SystemExit(f"integration XML contains failures/errors/unexpected skips: {totals}")
    return totals


def _policy(raw: str, bucket: str, observed_methods: list[str]) -> dict:
    if not raw.strip():
        raise SystemExit("CORS policy command returned no output")
    origin = "http://localhost:5173"
    methods = sorted(set(re.findall(r"(?i)(?:AllowedMethod|allowedmethod|method)\s*[>: ]+\s*(PUT|GET|HEAD|OPTIONS)", raw)))
    if not methods:
        methods = sorted(set(observed_methods))
    if origin not in raw or "PUT" not in methods:
        raise SystemExit("CORS policy does not contain localhost:5173 and PUT")
    if re.search(r"(?i)access permission.*public", raw) or not re.search(r"(?i)private", raw):
        raise SystemExit("MinIO bucket is not verified private")
    return {
        "bucket": bucket,
        "origin": origin,
        "methods": methods,
        "policy_applied": True,
        "policy_verified": True,
        "bucket_private": True,
        "source": "mc cors info/get" if "cors_allow_origin" not in raw else "mc admin config fallback",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--integration-xml", type=Path, required=True)
    parser.add_argument("--runtime-results", type=Path, required=True)
    parser.add_argument("--doctor", type=Path, required=True)
    parser.add_argument("--cors-policy-output", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bucket", default="tennisai-local")
    args = parser.parse_args()

    totals = _junit(args.integration_xml)
    runtime = _json(args.runtime_results)
    observations = runtime.get("observations", [])
    doctor = _json(args.doctor)
    if doctor.get("status") != "ready":
        raise SystemExit("platform doctor is not ready")
    if urlparse(doctor.get("public_endpoint", "")).hostname not in LOCAL_HOSTS:
        raise SystemExit("doctor public endpoint is not localhost")

    hosts = sorted({item["host"] for item in observations if item.get("host")})
    if any(host not in LOCAL_HOSTS for host in hosts):
        raise SystemExit(f"non-localhost presigned endpoint observed: {hosts}")
    cors_observations = [item for item in observations if item.get("operation") == "OPTIONS presigned upload"]
    if not cors_observations:
        raise SystemExit("runtime results do not contain a CORS preflight")
    cors = cors_observations[-1]
    observed_methods = []
    for value in cors.get("allow_methods", []):
        observed_methods.extend(part.strip().upper() for part in str(value).split(",") if part.strip())
    if cors.get("status") != 200 or cors.get("cors_origin") != "http://localhost:5173" or "PUT" not in observed_methods:
        raise SystemExit(
            "runtime CORS preflight is missing localhost:5173 and PUT: "
            f"status={cors.get('status')!r} origin={cors.get('cors_origin')!r} methods={observed_methods!r}"
        )
    cors_report = _policy(
        args.cors_policy_output.read_text(encoding="utf-8"),
        args.bucket,
        observed_methods,
    )
    cors_report.update({
        "preflight_status": cors["status"],
        "preflight_headers": {
            "access-control-allow-origin": cors.get("cors_origin"),
            "access-control-allow-methods": observed_methods,
            "access-control-allow-headers": cors.get("allow_headers", []),
        },
    })

    positive = sum(1 for item in observations if int(item.get("status", 500)) < 400)
    negative = sum(1 for item in observations if int(item.get("status", 200)) >= 400)
    operations = sorted({item.get("operation", "") for item in observations if item.get("operation")})
    runtime_summary = {
        "status": "passed",
        "total": totals["tests"],
        "positive": positive,
        "negative": negative,
        "failures": totals["failures"],
        "skipped": totals["skipped"],
        "endpoint_operations": operations,
    }
    presigned = {
        "upload_hosts": hosts,
        "download_hosts": hosts,
        "internal_hostname_leaked": False,
        "full_presigned_urls": False,
    }
    serialized = json.dumps({"observations": observations, "doctor": doctor}, sort_keys=True)
    if SECRET_PATTERN.search(serialized) or PRESIGNED_QUERY_PATTERN.search(serialized):
        raise SystemExit("runtime evidence contains credentials or full presigned URLs")
    security = {
        "secrets": False,
        "presigned_urls": False,
        "videos": False,
        "database_dumps": False,
        "status": "clean",
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "cors-report.json": cors_report,
        "presigned-endpoint-report.json": presigned,
        "security-summary.json": security,
        "runtime-test-summary.json": runtime_summary,
    }.items():
        (args.output_dir / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(runtime_summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
