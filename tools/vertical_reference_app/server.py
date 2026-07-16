"""HTTP server for the isolated vertical reference tool."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from tools.vertical_reference_app.core import VerticalReferenceError, VerticalReferenceSession


STATIC_ROOT = Path(__file__).with_name("static")


class VerticalReferenceHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], session: VerticalReferenceSession) -> None:
        super().__init__(address, VerticalReferenceRequestHandler)
        self.session = session


class VerticalReferenceRequestHandler(BaseHTTPRequestHandler):
    server: VerticalReferenceHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(payload, dict):
            raise VerticalReferenceError("El cuerpo debe ser un objeto JSON.")
        return payload

    def _file(self, path: Path, content_type: str | None = None) -> None:
        if not path.is_file():
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/session":
            self._json(self.server.session.session_payload())
            return
        if path == "/api/self-test":
            self._json(self.server.session.self_test)
            return
        if path == "/api/frame":
            self._file(self.server.session.frame_path, "image/png")
            return
        if path == "/":
            self._file(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
            return
        if path in {"/app.js", "/styles.css"}:
            self._file(STATIC_ROOT / path.removeprefix("/"))
            return
        self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            if not self.server.session.ready:
                raise VerticalReferenceError("La herramienta está bloqueada por self-test.")
            if path == "/api/reference":
                self._json(self.server.session.add_click(self._body().get("pixel")))
                return
            if path == "/api/reference/undo":
                self._json(self.server.session.undo())
                return
            if path == "/api/reference/reset":
                self._json(self.server.session.reset())
                return
            if path == "/api/reference/save":
                self._json(self.server.session.save())
                return
            self._json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
        except (VerticalReferenceError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)


def create_server(session: VerticalReferenceSession, port: int = 8766) -> VerticalReferenceHTTPServer:
    return VerticalReferenceHTTPServer(("127.0.0.1", port), session)
