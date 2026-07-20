from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis_bundle.builder import build_bundle
from .analysis_bundle.errors import (
    BundleBuildError,
    BundleInputError,
    BundleIntegrityError,
    BundlePathError,
    BundleSchemaError,
)
from .analysis_bundle.profiles import resolve_profile
from .analysis_bundle.validator import validate_bundle


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tennisai")
    sub = parser.add_subparsers(dest="command", required=True)
    bundle = sub.add_parser("bundle")
    bundle_sub = bundle.add_subparsers(dest="bundle_command", required=True)
    build = bundle_sub.add_parser("build")
    build.add_argument("--source-video", type=Path, required=True)
    build.add_argument("--inputs", type=Path, required=True)
    build.add_argument("--session-id", required=True)
    build.add_argument("--profile", required=True)
    build.add_argument("--surface", required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--created-at")
    build.add_argument("--core-version", default="0.1.0")
    build.add_argument("--overwrite", action="store_true")
    build.add_argument("--json", action="store_true")
    validate = bundle_sub.add_parser("validate")
    validate.add_argument("--bundle", type=Path, required=True)
    validate.add_argument("--verify-source", type=Path)
    validate.add_argument("--json", action="store_true")
    profile = sub.add_parser("profile")
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)
    show = profile_sub.add_parser("show")
    show.add_argument("name")
    show.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "profile":
            result = resolve_profile(args.name)
        elif args.bundle_command == "build":
            result = build_bundle(
                args.source_video,
                args.inputs,
                args.session_id,
                args.profile,
                args.surface,
                args.output,
                args.created_at,
                args.core_version,
                args.overwrite,
            )
        else:
            result = validate_bundle(args.bundle, args.verify_source)
        print(
            json.dumps(result, sort_keys=True)
            if getattr(args, "json", False)
            else _human(result, args)
        )
        return 0
    except (BundleInputError, BundleSchemaError, BundleIntegrityError, BundlePathError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3 if isinstance(exc, (BundleInputError, BundlePathError)) else 2
    except BundleBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


def _human(result: dict, args) -> str:
    if args.command == "profile":
        return json.dumps(result, indent=2, sort_keys=True)
    if args.bundle_command == "validate":
        return f"Bundle valid: {result['session_id']}\nFingerprint: {result['fingerprint']}\nFiles verified: {result['files_verified']}"
    return f"Bundle built: {result['session_id']}\nFingerprint: {result['fingerprint']}\nFiles verified: {result['files_verified']}"


if __name__ == "__main__":
    raise SystemExit(main())
