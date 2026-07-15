"""Localhost HTTP API and static frontend for the verified event annotator."""

from __future__ import annotations

import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from src.events.event_schema import EventValidationError
from tools.event_annotator_app.core import AnnotatorError, AnnotatorSession


STATIC_ROOT = Path(__file__).with_name("static")
FRAME_PATTERN = re.compile(r"^/api/frames/(\d+)$")
METADATA_PATTERN = re.compile(r"^/api/frames/(\d+)/metadata$")
EVENT_PATTERN = re.compile(r"^/api/events/([^/]+)$")


class AnnotatorHTTPServer(ThreadingHTTPServer):
    """Threading localhost server carrying one prepared annotator session."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], session: AnnotatorSession) -> None:
        super().__init__(address, AnnotatorRequestHandler)
        self.session = session


class AnnotatorRequestHandler(BaseHTTPRequestHandler):
    """Strict API: cached frames, metadata, event CRUD, undo, export, and self-test."""

    server: AnnotatorHTTPServer

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _body(self) -> Mapping[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError) as exc:
            raise AnnotatorError("Request body must be valid JSON") from exc
        if not isinstance(payload, Mapping):
            raise AnnotatorError("Request body must be a JSON object")
        return payload

    def _require_ready(self) -> None:
        if not self.server.session.ready:
            raise AnnotatorError("Herramienta no lista: self-test failed")

    def _send_file(self, path: Path, content_type: str | None = None) -> None:
        if not path.is_file():
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header(
            "Content-Type",
            content_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream",
        )
        self.send_header("Content-Length", str(len(data)))
        self.send_header(
            "Cache-Control", "public, max-age=31536000" if path.suffix == ".webp" else "no-cache"
        )
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/api/session":
                self._json(self.server.session.session_payload())
                return
            if path == "/api/self-test":
                self._json(self.server.session.self_test)
                return
            if path == "/api/events":
                self._json({"events": self.server.session.events.list()})
                return
            metadata_match = METADATA_PATTERN.fullmatch(path)
            if metadata_match:
                self._json(self.server.session.frame_metadata(int(metadata_match.group(1))))
                return
            frame_match = FRAME_PATTERN.fullmatch(path)
            if frame_match:
                image_path = self.server.session.frame_index.image_path(int(frame_match.group(1)))
                self._send_file(image_path, "image/webp")
                return
            if path in {"", "/"}:
                self._send_file(STATIC_ROOT / "index.html", "text/html; charset=utf-8")
                return
            static_name = path.removeprefix("/")
            if static_name in {"app.js", "styles.css"}:
                self._send_file(STATIC_ROOT / static_name)
                return
            self._error(HTTPStatus.NOT_FOUND, "Not found")
        except AnnotatorError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            self._require_ready()
            if path == "/api/events":
                event = self.server.session.events.create(self._body())
                self._json({"event": event, "autosaved": True}, HTTPStatus.CREATED)
                return
            if path == "/api/events/undo":
                self._json({"events": self.server.session.events.undo(), "autosaved": True})
                return
            if path == "/api/export":
                if not self.server.session.input_hashes_unchanged():
                    raise AnnotatorError("Original inputs changed after the readiness self-test")
                if self.server.session.frame_index.frame_count != 527:
                    raise AnnotatorError("Frame index no longer contains 527 frames")
                output = self.server.session.events.export()
                self._json({"exported": True, "filename": output.name})
                return
            self._error(HTTPStatus.NOT_FOUND, "Not found")
        except (AnnotatorError, EventValidationError, KeyError, TypeError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        match = EVENT_PATTERN.fullmatch(path)
        if match is None:
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            self._require_ready()
            event = self.server.session.events.update(match.group(1), self._body())
            self._json({"event": event, "autosaved": True})
        except (AnnotatorError, EventValidationError, KeyError, TypeError, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        match = EVENT_PATTERN.fullmatch(path)
        if match is None:
            self._error(HTTPStatus.NOT_FOUND, "Not found")
            return
        try:
            self._require_ready()
            self.server.session.events.delete(match.group(1))
            self._json({"deleted": True, "autosaved": True})
        except AnnotatorError as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))


def create_server(session: AnnotatorSession, port: int = 8765) -> AnnotatorHTTPServer:
    """Bind the application exclusively to the IPv4 loopback interface."""
    return AnnotatorHTTPServer(("127.0.0.1", port), session)
