from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode()


def bundle_fingerprint(
    manifest_without_fingerprint: dict[str, Any], checksums: dict[str, str], source_sha256: str
) -> str:
    payload = {
        "manifest": manifest_without_fingerprint,
        "checksums": dict(sorted(checksums.items())),
        "source_video_sha256": source_sha256,
    }
    return hashlib.sha256(canonical_json(payload)).hexdigest()
