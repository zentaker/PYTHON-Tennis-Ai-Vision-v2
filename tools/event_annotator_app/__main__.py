"""Run the verified Stage 4 annotator on localhost."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from tools.event_annotator_app.core import AnnotatorSession, SessionConfig
from tools.event_annotator_app.server import create_server


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0 <= args.port <= 65535:
        print("ERROR: --port must be between 0 and 65535", file=sys.stderr)
        return 2
    try:
        session = AnnotatorSession(
            SessionConfig(video_path=args.video, clip_id=args.clip_id),
            progress=lambda message: print(message, flush=True),
        )
        server = create_server(session, args.port)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Self-test: {session.self_test['status']}", flush=True)
    print(f"URL: {url}", flush=True)
    if not session.ready:
        print("Herramienta no lista", file=sys.stderr, flush=True)
    elif not args.no_open and sys.platform == "darwin":
        subprocess.Popen(["open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.", flush=True)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
