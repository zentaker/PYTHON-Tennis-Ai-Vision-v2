"""Stage 0 environment verification."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ok(message: str) -> None:
    print(f"[OK] {message}")


def warn(message: str) -> None:
    print(f"[WARN] {message}")


def fail(message: str, failures: list[str]) -> None:
    print(f"[FAIL] {message}")
    failures.append(message)


def check_python(failures: list[str]) -> None:
    version = sys.version_info
    if version.major == 3 and version.minor == 11:
        ok(f"Python {platform.python_version()}")
    else:
        fail(f"Python 3.11.x requerido; encontrado {platform.python_version()}", failures)


def check_wsl_ubuntu(failures: list[str]) -> None:
    if platform.system() != "Linux":
        fail("El script debe correr dentro de WSL2/Linux para el gate final", failures)
        return

    os_release = Path("/etc/os-release")
    if not os_release.exists():
        fail("No existe /etc/os-release", failures)
        return

    content = os_release.read_text(encoding="utf-8")
    if "Ubuntu" not in content:
        fail("El sistema Linux detectado no reporta Ubuntu", failures)
        return

    if 'VERSION_ID="24.04"' in content or "VERSION_ID=24.04" in content:
        ok("Ubuntu 24.04 detectado")
    else:
        fail("Ubuntu 24.04 requerido; /etc/os-release reporta otra version", failures)


def check_imports(failures: list[str]) -> None:
    try:
        import numpy as np
    except Exception as exc:  # pragma: no cover - diagnostic path
        fail(f"NumPy no importa: {exc}", failures)
    else:
        major = int(np.__version__.split(".", maxsplit=1)[0])
        if major < 2:
            ok(f"NumPy {np.__version__}")
        else:
            fail(f"NumPy <2.0 requerido; encontrado {np.__version__}", failures)

    try:
        import cv2
    except Exception as exc:  # pragma: no cover - diagnostic path
        fail(f"OpenCV no importa: {exc}", failures)
    else:
        ok(f"OpenCV {cv2.__version__}")

    try:
        import scipy
    except Exception as exc:  # pragma: no cover - diagnostic path
        fail(f"SciPy no importa: {exc}", failures)
    else:
        ok(f"SciPy {scipy.__version__}")


def check_paths(failures: list[str]) -> None:
    for rel_path in ("data", "data/reference_clip", "models", "models/wasb", "outputs"):
        path = ROOT / rel_path
        if path.exists():
            ok(f"Ruta existe: {rel_path}")
        else:
            fail(f"Ruta faltante: {rel_path}", failures)


def check_reference_assets(failures: list[str]) -> None:
    try:
        import cv2
    except Exception:
        warn("No se valida clip/frame porque OpenCV no esta disponible")
        return

    clip_path = ROOT / "data/reference_clip/madrid_R1.mp4"
    frame_path = ROOT / "data/reference_clip/reference_frame.png"
    annotation_path = ROOT / "data/reference_clip/manual_annotation.json"

    if clip_path.exists():
        capture = cv2.VideoCapture(str(clip_path))
        success, _frame = capture.read()
        capture.release()
        if success:
            ok("OpenCV puede leer un frame de madrid_R1.mp4")
        else:
            fail("OpenCV no pudo leer frames de madrid_R1.mp4", failures)
    else:
        warn("Clip local no encontrado: data/reference_clip/madrid_R1.mp4")

    if frame_path.exists():
        image = cv2.imread(str(frame_path))
        if image is not None:
            ok("reference_frame.png se puede abrir")
        else:
            fail("reference_frame.png existe pero no se puede abrir", failures)
    else:
        warn("Frame de referencia no encontrado: data/reference_clip/reference_frame.png")

    if annotation_path.exists():
        try:
            payload = json.loads(annotation_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            fail(f"manual_annotation.json no es JSON valido: {exc}", failures)
            return

        required_keys = {
            "clip_path",
            "level",
            "fps",
            "duration_seconds",
            "frames_total",
            "court_corners_pixel",
            "service_box_corners_pixel",
            "players",
            "narrative_events",
            "ball_manual_positions",
        }
        missing = sorted(required_keys.difference(payload))
        if missing:
            fail(f"manual_annotation.json incompleto; faltan claves: {', '.join(missing)}", failures)
        else:
            ok("manual_annotation.json tiene las claves requeridas")
    else:
        warn("Anotacion local no encontrada: data/reference_clip/manual_annotation.json")


def main() -> int:
    failures: list[str] = []
    check_python(failures)
    check_wsl_ubuntu(failures)
    check_imports(failures)
    check_paths(failures)
    check_reference_assets(failures)

    if failures:
        print()
        print(f"Verificacion fallida: {len(failures)} problema(s) critico(s).")
        return 1

    print()
    print("Verificacion completada sin fallas criticas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
