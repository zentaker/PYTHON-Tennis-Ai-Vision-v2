"""Local browser-based manual court calibration."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import cv2

if __package__ in (None, ""):
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.court.coordinates import CALIBRATION_POINT_ORDER, CalibrationLayout


POINT_DESCRIPTIONS: dict[str, str] = {
    "far_left": "esquina lejana izquierda, doubles sideline ∩ baseline lejana",
    "far_right": "esquina lejana derecha, doubles sideline ∩ baseline lejana",
    "near_left": "esquina cercana izquierda, doubles sideline ∩ baseline cercana",
    "near_right": "esquina cercana derecha, doubles sideline ∩ baseline cercana",
    "far_left_service": "singles sideline izquierda ∩ service line lejana",
    "far_right_service": "singles sideline derecha ∩ service line lejana",
    "near_left_service": "singles sideline izquierda ∩ service line cercana",
    "near_right_service": "singles sideline derecha ∩ service line cercana",
}


def image_size(image_path: Path) -> tuple[int, int]:
    """Return image width and height in pixels."""
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(f"Could not open image: {image_path}")
    height, width = image.shape[:2]
    return int(width), int(height)


def sanitize_points(raw_points: Any) -> dict[str, tuple[int, int]]:
    """Convert browser JSON payload into an ordered point dictionary."""
    if not isinstance(raw_points, list):
        raise ValueError("Payload must contain a list of points")
    if len(raw_points) != len(CALIBRATION_POINT_ORDER):
        raise ValueError(f"Expected {len(CALIBRATION_POINT_ORDER)} points, got {len(raw_points)}")

    points: dict[str, tuple[int, int]] = {}
    for index, expected_name in enumerate(CALIBRATION_POINT_ORDER, start=1):
        item = raw_points[index - 1]
        if not isinstance(item, dict):
            raise ValueError(f"Point {index} is not an object")
        name = item.get("name")
        if name != expected_name:
            raise ValueError(f"Point {index} must be {expected_name}, got {name}")
        try:
            x = int(round(float(item["x"])))
            y = int(round(float(item["y"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Point {index} has invalid coordinates") from exc
        points[expected_name] = (x, y)
    return points


def validate_calibration_points(
    points: dict[str, tuple[int, int]],
    width: int,
    height: int,
) -> list[str]:
    """Run Stage 1 fallback sanity checks before persisting clicks."""
    errors: list[str] = []

    for name in CALIBRATION_POINT_ORDER:
        if name not in points:
            errors.append(f"Falta el punto {name}")
            continue
        x, y = points[name]
        if not (0 <= x < width and 0 <= y < height):
            errors.append(f"{name} fuera de bounds: ({x}, {y}) no está dentro de {width}x{height}")

    pairs = (
        ("far_left", "far_right"),
        ("near_left", "near_right"),
        ("far_left_service", "far_right_service"),
        ("near_left_service", "near_right_service"),
    )
    for left_name, right_name in pairs:
        if left_name in points and right_name in points:
            if points[left_name][0] >= points[right_name][0]:
                errors.append(f"Orden izquierda/derecha inválido: {left_name} debe estar a la izquierda de {right_name}")

    far_near_pairs = (
        ("far_left", "near_left"),
        ("far_right", "near_right"),
        ("far_left_service", "near_left_service"),
        ("far_right_service", "near_right_service"),
    )
    for far_name, near_name in far_near_pairs:
        if far_name in points and near_name in points:
            if points[far_name][1] >= points[near_name][1]:
                errors.append(f"Orden far/near inválido: {far_name} debe estar más arriba que {near_name}")

    if all(name in points for name in CALIBRATION_POINT_ORDER):
        far_top = max(points["far_left"][1], points["far_right"][1])
        near_bottom = min(points["near_left"][1], points["near_right"][1])
        left_bound = min(points["far_left"][0], points["near_left"][0])
        right_bound = max(points["far_right"][0], points["near_right"][0])

        for name in (
            "far_left_service",
            "far_right_service",
            "near_left_service",
            "near_right_service",
        ):
            x, y = points[name]
            if not (left_bound <= x <= right_bound and far_top <= y <= near_bottom):
                errors.append(f"{name} no cae dentro del rectángulo de doubles")

    return errors


def calibration_payload(
    points: dict[str, tuple[int, int]],
    image_path: Path,
    guide_path: Path,
    layout: CalibrationLayout,
    method: str = "manual_web_click",
) -> dict[str, object]:
    """Build the JSON payload persisted after successful browser clicks."""
    return {
        "image_path": str(image_path),
        "guide_path": str(guide_path),
        "layout": layout,
        "method": method,
        "point_order": list(CALIBRATION_POINT_ORDER),
        "court_corners_pixel": {
            name: [int(points[name][0]), int(points[name][1])] for name in CALIBRATION_POINT_ORDER
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def write_calibration_json(
    output_path: Path,
    points: dict[str, tuple[int, int]],
    image_path: Path,
    guide_path: Path,
    layout: CalibrationLayout,
) -> None:
    """Persist a successful browser calibration JSON file."""
    payload = calibration_payload(points, image_path, guide_path, layout)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def render_html(width: int, height: int) -> str:
    """Return the calibration web page."""
    point_payload = [
        {"name": name, "description": POINT_DESCRIPTIONS[name], "index": index}
        for index, name in enumerate(CALIBRATION_POINT_ORDER, start=1)
    ]
    points_json = json.dumps(point_payload, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stage 1 Court Calibration</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #111; color: #f4f4f4; }}
    header {{ position: sticky; top: 0; z-index: 10; background: #111; border-bottom: 1px solid #333; padding: 12px 16px; }}
    .current {{ font-size: 18px; font-weight: 700; margin-bottom: 4px; }}
    .description {{ color: #d6d6d6; margin-bottom: 10px; }}
    .guide {{ display: flex; align-items: center; gap: 12px; }}
    .guide img {{ width: 320px; height: auto; border: 1px solid #555; }}
    .controls {{ padding: 12px 16px; display: flex; gap: 10px; align-items: center; }}
    button {{ padding: 8px 12px; font-size: 14px; cursor: pointer; }}
    #status {{ color: #9fd6ff; }}
    #errors {{ color: #ffb3b3; white-space: pre-wrap; padding: 0 16px 12px; }}
    #stage {{ position: relative; width: {width}px; height: {height}px; margin: 0 16px 24px; }}
    #frame {{ display: block; width: {width}px; height: {height}px; max-width: none; max-height: none; cursor: crosshair; }}
    .marker {{ position: absolute; width: 22px; height: 22px; border-radius: 50%; transform: translate(-50%, -50%); background: #ff1f1f; color: white; border: 2px solid white; font-weight: 700; font-size: 13px; line-height: 22px; text-align: center; pointer-events: none; box-shadow: 0 0 0 2px #111; }}
  </style>
</head>
<body>
  <header>
    <div id="current" class="current"></div>
    <div id="description" class="description"></div>
    <div class="guide">
      <img src="/calibration_guide.png" alt="Guía de calibración">
      <div>Usá la guía chica solo como referencia. Hacé los clics sobre la imagen grande de abajo.</div>
    </div>
  </header>
  <div class="controls">
    <button id="undo">Repetir último punto</button>
    <button id="reset">Reiniciar</button>
    <span id="status"></span>
  </div>
  <div id="errors"></div>
  <div id="stage">
    <img id="frame" src="/reference_frame.png" alt="Reference frame" width="{width}" height="{height}">
  </div>
  <script>
    const points = {points_json};
    const clicked = [];
    const stage = document.getElementById("stage");
    const frame = document.getElementById("frame");
    const current = document.getElementById("current");
    const description = document.getElementById("description");
    const statusEl = document.getElementById("status");
    const errorsEl = document.getElementById("errors");

    function updateHeader() {{
      if (clicked.length >= points.length) {{
        current.textContent = "8/8 puntos capturados";
        description.textContent = "Validando y guardando calibración...";
      }} else {{
        const point = points[clicked.length];
        current.textContent = `${{point.index}}/8: ${{point.name}}`;
        description.textContent = point.description;
      }}
      statusEl.textContent = `${{clicked.length}} puntos capturados`;
    }}

    function redrawMarkers() {{
      document.querySelectorAll(".marker").forEach((marker) => marker.remove());
      clicked.forEach((point, idx) => {{
        const marker = document.createElement("div");
        marker.className = "marker";
        marker.textContent = String(idx + 1);
        marker.style.left = `${{point.x}}px`;
        marker.style.top = `${{point.y}}px`;
        stage.appendChild(marker);
      }});
    }}

    function resetAll(message = "") {{
      clicked.splice(0, clicked.length);
      errorsEl.textContent = message;
      redrawMarkers();
      updateHeader();
    }}

    async function submitPoints() {{
      errorsEl.textContent = "";
      const response = await fetch("/submit", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ points: clicked }}),
      }});
      const payload = await response.json();
      if (!response.ok) {{
        resetAll(`Sanity checks fallaron:\\n- ${{payload.errors.join("\\n- ")}}\\n\\nReiniciá y volvé a clickear los 8 puntos.`);
        return;
      }}
      current.textContent = "Calibración guardada";
      description.textContent = "Podés cerrar esta ventana.";
      statusEl.textContent = payload.output;
    }}

    frame.addEventListener("click", (event) => {{
      if (clicked.length >= points.length) return;
      const rect = frame.getBoundingClientRect();
      const x = Math.round(event.clientX - rect.left);
      const y = Math.round(event.clientY - rect.top);
      const point = points[clicked.length];
      clicked.push({{ name: point.name, x, y }});
      redrawMarkers();
      updateHeader();
      if (clicked.length === points.length) {{
        submitPoints().catch((error) => {{
          resetAll(`Error enviando calibración: ${{error}}`);
        }});
      }}
    }});

    document.getElementById("undo").addEventListener("click", () => {{
      clicked.pop();
      errorsEl.textContent = "";
      redrawMarkers();
      updateHeader();
    }});

    document.getElementById("reset").addEventListener("click", () => {{
      resetAll();
    }});

    updateHeader();
  </script>
</body>
</html>
"""


class CalibrationServer(ThreadingHTTPServer):
    """HTTP server carrying calibration paths and shutdown state."""

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        image_path: Path,
        guide_path: Path,
        output_path: Path,
        layout: CalibrationLayout,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.image_path = image_path
        self.guide_path = guide_path
        self.output_path = output_path
        self.layout = layout
        self.image_width, self.image_height = image_size(image_path)


class CalibrationRequestHandler(BaseHTTPRequestHandler):
    """Request handler for the local calibration UI."""

    server: CalibrationServer

    def log_message(self, format: str, *args: object) -> None:
        print(f"[calibrate_web] {self.address_string()} - {format % args}")

    def send_bytes(self, payload: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            html = render_html(self.server.image_width, self.server.image_height)
            self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
            return
        if self.path == "/reference_frame.png":
            self.serve_file(self.server.image_path)
            return
        if self.path == "/calibration_guide.png":
            self.serve_file(self.server.guide_path)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        if self.path != "/submit":
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
            points = sanitize_points(payload.get("points"))
            errors = validate_calibration_points(points, self.server.image_width, self.server.image_height)
        except ValueError as exc:
            errors = [str(exc)]
            points = {}

        if errors:
            response = json.dumps({"ok": False, "errors": errors}, ensure_ascii=False).encode("utf-8")
            self.send_bytes(response, "application/json; charset=utf-8", HTTPStatus.BAD_REQUEST)
            return

        write_calibration_json(
            self.server.output_path,
            points,
            self.server.image_path,
            self.server.guide_path,
            self.server.layout,
        )
        response = json.dumps(
            {"ok": True, "output": str(self.server.output_path)},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_bytes(response, "application/json; charset=utf-8")
        threading.Timer(2.0, self.server.shutdown).start()

    def serve_file(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, f"File not found: {path}")
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_bytes(path.read_bytes(), content_type)


def run_server(
    host: str,
    port: int,
    image_path: Path,
    guide_path: Path,
    output_path: Path,
    layout: CalibrationLayout,
) -> None:
    """Run the local calibration server until a successful POST shuts it down."""
    server = CalibrationServer(
        (host, port),
        CalibrationRequestHandler,
        image_path,
        guide_path,
        output_path,
        layout,
    )
    print(f"Serving calibration UI at http://{host}:{port}")
    print(f"Image size: {server.image_width}x{server.image_height}")
    try:
        server.serve_forever()
    finally:
        server.server_close()
        print("Calibration server stopped")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--image", type=Path, default=Path("data/reference_clip/reference_frame.png"))
    parser.add_argument("--guide", type=Path, default=Path("outputs/stage_1/calibration_guide.png"))
    parser.add_argument("--output", type=Path, default=Path("data/reference_clip/court_corners_pixel.json"))
    parser.add_argument("--layout", choices=("doubles", "singles"), default="doubles")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_server(args.host, args.port, args.image, args.guide, args.output, args.layout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
