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
from .single_rally.errors import SingleRallyError
from .single_rally.importer import import_single_rally
from .single_rally.validation import validate_single_rally_bundle


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
    rally = sub.add_parser("rally")
    rally_sub = rally.add_subparsers(dest="rally_command", required=True)
    rally_import = rally_sub.add_parser("import")
    rally_import.add_argument("--source-video", type=Path, required=True)
    rally_import.add_argument("--inputs", type=Path, required=True)
    rally_import.add_argument("--session-id", required=True)
    rally_import.add_argument("--rally-id", required=True)
    rally_import.add_argument("--profile", required=True)
    rally_import.add_argument("--surface", required=True)
    rally_import.add_argument("--output", type=Path, required=True)
    rally_import.add_argument("--created-at")
    rally_import.add_argument("--overwrite", action="store_true")
    rally_import.add_argument("--json", action="store_true")
    rally_validate = rally_sub.add_parser("validate")
    rally_validate.add_argument("--bundle", type=Path, required=True)
    rally_validate.add_argument("--json", action="store_true")
    platform = sub.add_parser("platform", help="local Session Platform commands")
    platform_sub = platform.add_subparsers(dest="platform_command", required=True)
    platform_sub.add_parser("migrate")
    platform_sub.add_parser("doctor")
    platform_sub.add_parser("seed-stage1b-reference")
    api = platform_sub.add_parser("api")
    api.add_argument("--host")
    api.add_argument("--port", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "platform":
            return _platform_main(args)
        if args.command == "profile":
            result = resolve_profile(args.name)
        elif args.command == "rally":
            if args.rally_command == "import":
                result = import_single_rally(
                    args.source_video,
                    args.inputs,
                    args.session_id,
                    args.rally_id,
                    args.profile,
                    args.surface,
                    args.output,
                    args.created_at,
                    args.overwrite,
                )
            else:
                result = validate_single_rally_bundle(args.bundle)
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
    except (
        BundleInputError,
        BundleSchemaError,
        BundleIntegrityError,
        BundlePathError,
        SingleRallyError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3 if isinstance(exc, (BundleInputError, BundlePathError)) else 2
    except BundleBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4


def _platform_main(args) -> int:
    """Lazy platform entrypoint so core CLI imports remain infrastructure-free."""
    if args.platform_command == "api":
        import uvicorn

        from src.platform.api.app import create_app
        from src.platform.config.settings import get_settings

        settings = get_settings()
        uvicorn.run(
            create_app(), host=args.host or settings.api_host, port=args.port or settings.api_port
        )
        return 0
    if args.platform_command == "migrate":
        import subprocess

        completed = subprocess.run(["alembic", "upgrade", "head"], check=False)
        return completed.returncode
    if args.platform_command == "doctor":
        from src.platform.services.doctor import doctor

        result = doctor()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "ready" else 1
    if args.platform_command == "seed-stage1b-reference":
        from src.platform.services.seed import seed_stage1b_reference

        print(json.dumps(seed_stage1b_reference(), sort_keys=True))
        return 0
    raise ValueError(f"unknown platform command: {args.platform_command}")


def _human(result: dict, args) -> str:
    if args.command == "profile":
        return json.dumps(result, indent=2, sort_keys=True)
    if args.command == "rally":
        return f"Single rally valid: {result['rally_id']}\nFingerprint: {result['fingerprint']}"
    if args.bundle_command == "validate":
        return f"Bundle valid: {result['session_id']}\nFingerprint: {result['fingerprint']}\nFiles verified: {result['files_verified']}"
    return f"Bundle built: {result['session_id']}\nFingerprint: {result['fingerprint']}\nFiles verified: {result['files_verified']}"


if __name__ == "__main__":
    raise SystemExit(main())
