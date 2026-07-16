"""Run the local Stage 5A.1 vertical reference tool."""

from __future__ import annotations

import argparse
import subprocess
import sys

from tools.vertical_reference_app.core import VerticalReferenceSession
from tools.vertical_reference_app.server import create_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clip-id", required=True)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--open-browser", action="store_true", help="Abrir explícitamente el navegador")
    parser.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        print("ERROR: --port debe estar entre 0 y 65535", file=sys.stderr)
        return 2
    try:
        session = VerticalReferenceSession(args.clip_id)
        server = create_server(session, args.port)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    host, port = server.server_address
    url = f"http://{host}:{port}/"
    print(f"Self-test: {session.self_test['status']}", flush=True)
    print(f"URL: {url}", flush=True)
    if not session.ready:
        print("Herramienta bloqueada: self-test fallido", file=sys.stderr, flush=True)
    elif args.open_browser and not args.no_open and sys.platform == "darwin":
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
