from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ALLOWED_SUFFIXES = {".json", ".xml", ".txt", ".md"}
PATTERNS = {
    "lease_token": re.compile(r"(?i)(lease[_ -]?token\s*[:=]|token=)[A-Za-z0-9._-]{8,}"),
    "signed_url": re.compile(r"(?i)(x-amz-signature|x-amz-credential|signature=|presign)"),
    "credential": re.compile(r"(?i)(aws_secret_access_key|aws_access_key_id|password=|secret[_-]?key)"),
    "database_credential_url": re.compile(r"(?i)postgres(?:ql)?(?:\+\w+)?://[^\s/]+:[^\s/@]+@"),
    "absolute_workspace_path": re.compile(r"/(?:tmp|private|Users|home)/[^\s\"']+"),
    "traceback": re.compile(r"Traceback \(most recent call last\)"),
    "video_bytes_or_file": re.compile(r"(?i)\.(?:mp4|mov|avi|mkv|webm)\b"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    violations: list[dict[str, str]] = []
    scanned: list[str] = []
    for path in sorted(p for p in args.evidence_dir.rglob("*") if p.is_file()):
        relative = str(path.relative_to(args.evidence_dir))
        scanned.append(relative)
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            violations.append({"file": relative, "pattern": "unsupported_file_type"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern in PATTERNS.items():
            if pattern.search(text):
                violations.append({"file": relative, "pattern": name})
    evidence_path = args.evidence_dir / "worker-runtime-evidence.json"
    if evidence_path.exists():
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        for claim, support in evidence.get("supporting_tests", {}).items():
            if support.get("passed") is not True or not support.get("tests"):
                violations.append({"file": str(evidence_path.relative_to(args.evidence_dir)), "pattern": f"unsupported_claim:{claim}"})
    summary = {"files_scanned": scanned, "patterns_checked": sorted(PATTERNS), "violations": violations, "status": "failed" if violations else "passed"}
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
