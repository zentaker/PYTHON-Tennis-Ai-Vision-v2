"""Frame indexing, event persistence, and self-tests for the Stage 4 annotator."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import shutil
import tempfile
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

import cv2

from src.events.event_loader import load_normalized_events, normalize_annotation
from src.events.event_schema import normalize_narrative_event
from src.project.clip_manifest import ClipManifest
from src.video.canonical_frames import iter_canonical_frames
from src.video.frame_timestamps import (
    FrameTimestamp,
    FrameTimestampSidecar,
    build_frame_timestamp_sidecar,
    timestamp_values,
    validate_sidecar_against_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"
PRESETS: dict[str, dict[str, str]] = {
    "serve_near": {"type": "serve", "player": "near", "side": "near", "shot_type": "saque"},
    "serve_far": {"type": "serve", "player": "far", "side": "far", "shot_type": "saque"},
    "hit_near": {"type": "hit", "player": "near", "side": "near", "shot_type": "unknown"},
    "hit_far": {"type": "hit", "player": "far", "side": "far", "shot_type": "unknown"},
    "bounce_near": {"type": "bounce", "player": "unknown", "side": "near", "shot_type": "unknown"},
    "bounce_far": {"type": "bounce", "player": "unknown", "side": "far", "shot_type": "unknown"},
    "bounce_unknown": {
        "type": "bounce",
        "player": "unknown",
        "side": "unknown",
        "shot_type": "unknown",
    },
    "unknown": {"type": "unknown", "player": "unknown", "side": "unknown", "shot_type": "unknown"},
}


class AnnotatorError(ValueError):
    """Raised when the verified annotator contract is violated."""


def sha256_file(path: Path) -> str:
    """Hash a file without loading it into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class FrameRecord:
    frame_id: int
    timestamp_seconds: float
    duration_seconds: float
    cache_path: str
    image_sha256: str
    duplicate_visual_content: bool


@dataclass(frozen=True)
class SessionConfig:
    video_path: Path
    clip_id: str
    cache_root: Path = PROJECT_ROOT / ".cache" / "event_annotator"
    manifest_path: Path | None = None
    timestamps_path: Path | None = None
    tracking_path: Path | None = None
    draft_path: Path | None = None
    annotation_path: Path | None = None

    def resolved(self) -> SessionConfig:
        video = self.video_path.resolve()
        clip_dir = video.parent
        output_dir = PROJECT_ROOT / "outputs" / self.clip_id / "stage_4"
        return SessionConfig(
            video_path=video,
            clip_id=self.clip_id,
            cache_root=self.cache_root.resolve(),
            manifest_path=(self.manifest_path or clip_dir / "clip_manifest.json").resolve(),
            timestamps_path=(self.timestamps_path or clip_dir / "frame_timestamps.json").resolve(),
            tracking_path=(
                self.tracking_path
                or PROJECT_ROOT / "outputs" / self.clip_id / "stage_3" / "smoothed_trajectory.csv"
            ).resolve(),
            draft_path=(self.draft_path or output_dir / "annotation_draft.json").resolve(),
            annotation_path=(self.annotation_path or clip_dir / "manual_annotation.json").resolve(),
        )


class FrameIndex:
    """Exact one-to-one mapping between logical IDs and cached canonical images."""

    def __init__(
        self,
        *,
        cache_dir: Path,
        video_sha256: str,
        clip_id: str,
        width: int,
        height: int,
        duration_seconds: float,
        records: list[FrameRecord],
    ) -> None:
        self.cache_dir = cache_dir
        self.video_sha256 = video_sha256
        self.clip_id = clip_id
        self.width = width
        self.height = height
        self.duration_seconds = duration_seconds
        self.records = records
        self._validate()

    def _validate(self) -> None:
        ids = [record.frame_id for record in self.records]
        if ids != list(range(len(self.records))):
            raise AnnotatorError("Frame index IDs must be unique, consecutive, and start at zero")
        previous = -1.0
        paths: set[str] = set()
        for record in self.records:
            if record.timestamp_seconds <= previous and record.frame_id:
                raise AnnotatorError("Frame index timestamps must be strictly increasing")
            if record.duration_seconds <= 0 or not math.isfinite(record.duration_seconds):
                raise AnnotatorError(f"Invalid frame duration at {record.frame_id}")
            if record.cache_path in paths:
                raise AnnotatorError("Every frame ID must have a distinct cache path")
            paths.add(record.cache_path)
            previous = record.timestamp_seconds

    @property
    def frame_count(self) -> int:
        return len(self.records)

    def record(self, frame_id: int) -> FrameRecord:
        if isinstance(frame_id, bool) or not isinstance(frame_id, int):
            raise AnnotatorError("frame_id must be an integer")
        if frame_id < 0 or frame_id >= self.frame_count:
            raise AnnotatorError(f"frame_id {frame_id} outside 0–{self.frame_count - 1}")
        return self.records[frame_id]

    def image_path(self, frame_id: int) -> Path:
        return self.cache_dir / self.record(frame_id).cache_path

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "video_sha256": self.video_sha256,
            "clip_id": self.clip_id,
            "frame_count": self.frame_count,
            "first_frame_id": 0,
            "last_frame_id": self.frame_count - 1,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "frames": [asdict(record) for record in self.records],
        }

    @classmethod
    def read(cls, index_path: Path) -> FrameIndex:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise AnnotatorError("Unsupported frame index schema")
        records = [FrameRecord(**item) for item in payload["frames"]]
        return cls(
            cache_dir=index_path.parent,
            video_sha256=payload["video_sha256"],
            clip_id=payload["clip_id"],
            width=int(payload["width"]),
            height=int(payload["height"]),
            duration_seconds=float(payload["duration_seconds"]),
            records=records,
        )


def _load_timeline(config: SessionConfig, manifest: ClipManifest) -> FrameTimestampSidecar:
    timestamps_path = config.timestamps_path
    if timestamps_path is not None and timestamps_path.exists():
        sidecar = FrameTimestampSidecar.read(timestamps_path)
    else:
        sidecar = build_frame_timestamp_sidecar(config.video_path, manifest)
    validate_sidecar_against_manifest(sidecar, manifest)
    return sidecar


def _cache_is_complete(index: FrameIndex, manifest: ClipManifest, video_sha256: str) -> bool:
    if (
        index.video_sha256 != video_sha256
        or index.clip_id != manifest.clip_id
        or index.frame_count != manifest.frames_total
        or (index.width, index.height) != (manifest.canonical_width, manifest.canonical_height)
    ):
        return False
    return all(index.image_path(frame_id).is_file() for frame_id in range(index.frame_count))


def build_frame_index(
    config: SessionConfig,
    *,
    progress: Callable[[str], None] | None = None,
) -> tuple[FrameIndex, ClipManifest, FrameTimestampSidecar]:
    """Build or load a verified canonical WebP cache for one immutable video."""
    config = config.resolved()
    notify = progress or (lambda _message: None)
    if not config.video_path.is_file():
        raise AnnotatorError(f"Video not found: {config.video_path}")
    if config.manifest_path is None or not config.manifest_path.is_file():
        raise AnnotatorError(f"Manifest not found: {config.manifest_path}")
    manifest = ClipManifest.read(config.manifest_path)
    if manifest.clip_id != config.clip_id:
        raise AnnotatorError("CLI clip_id does not match the clip manifest")
    video_sha256 = sha256_file(config.video_path)
    if video_sha256 != manifest.source_sha256:
        raise AnnotatorError("Video SHA-256 does not match the clip manifest")
    sidecar = _load_timeline(config, manifest)

    cache_dir = config.cache_root / video_sha256
    index_path = cache_dir / "frame_index.json"
    if index_path.is_file():
        try:
            cached = FrameIndex.read(index_path)
            if _cache_is_complete(cached, manifest, video_sha256):
                notify(f"Using verified frame cache: {cache_dir}")
                return cached, manifest, sidecar
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass

    notify(f"Decoding {manifest.frames_total} canonical frames…")
    config.cache_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{video_sha256[:12]}-", dir=config.cache_root))
    frames_dir = temporary / "frames"
    frames_dir.mkdir(parents=True)
    records: list[FrameRecord] = []
    try:
        timeline = list(sidecar.frames)
        for decoded in iter_canonical_frames(
            config.video_path,
            manifest,
            timestamps=timestamp_values(timeline),
        ):
            timing: FrameTimestamp = timeline[decoded.frame_id]
            filename = f"frame_{decoded.frame_id:06d}.webp"
            image_path = frames_dir / filename
            if not cv2.imwrite(
                str(image_path),
                decoded.image_bgr,
                [cv2.IMWRITE_WEBP_QUALITY, 88],
            ):
                raise AnnotatorError(f"Could not write cache frame {decoded.frame_id}")
            image_hash = hashlib.sha256(decoded.image_bgr.tobytes()).hexdigest()
            records.append(
                FrameRecord(
                    frame_id=decoded.frame_id,
                    timestamp_seconds=timing.timestamp_seconds,
                    duration_seconds=timing.duration_seconds,
                    cache_path=f"frames/{filename}",
                    image_sha256=image_hash,
                    duplicate_visual_content=False,
                )
            )
            if decoded.frame_id % 50 == 0 or decoded.frame_id == manifest.frames_total - 1:
                notify(f"Indexed frame {decoded.frame_id}/{manifest.frames_total - 1}")

        counts = Counter(record.image_sha256 for record in records)
        records = [
            FrameRecord(
                **{
                    **asdict(record),
                    "duplicate_visual_content": counts[record.image_sha256] > 1,
                }
            )
            for record in records
        ]
        frame_index = FrameIndex(
            cache_dir=temporary,
            video_sha256=video_sha256,
            clip_id=manifest.clip_id,
            width=manifest.canonical_width,
            height=manifest.canonical_height,
            duration_seconds=sidecar.frames[-1].timestamp_seconds
            + sidecar.frames[-1].duration_seconds,
            records=records,
        )
        (temporary / "frame_index.json").write_text(
            json.dumps(frame_index.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        temporary.replace(cache_dir)
        return FrameIndex.read(cache_dir / "frame_index.json"), manifest, sidecar
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


class NavigationState:
    """Small deterministic navigation model shared by tests and self-test."""

    def __init__(self, frame_index: FrameIndex, start: int = 0) -> None:
        self.frame_index = frame_index
        self.current = self.frame_index.record(start).frame_id

    def jump(self, frame_id: int) -> int:
        self.current = self.frame_index.record(frame_id).frame_id
        return self.current

    def move(self, delta: int) -> int:
        return self.jump(self.current + delta)


def load_tracking(path: Path | None, frame_count: int) -> dict[int, dict[str, object]]:
    """Load optional smoothed tracking without making it an annotator requirement."""
    if path is None or not path.is_file():
        return {}
    tracking: dict[int, dict[str, object]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            frame_id = int(row["frame_id"])
            if not 0 <= frame_id < frame_count:
                raise AnnotatorError("Tracking frame outside the frame index")
            x_value = row.get("x_smooth", "")
            y_value = row.get("y_smooth", "")
            tracking[frame_id] = {
                "x": None if x_value == "" else float(x_value),
                "y": None if y_value == "" else float(y_value),
                "source": row.get("source", "missing"),
            }
    if set(tracking) != set(range(frame_count)):
        raise AnnotatorError("Tracking rows must match the complete frame index")
    return tracking


class EventStore:
    """Thread-safe event CRUD with atomic autosave, undo, restore, and export."""

    def __init__(
        self,
        frame_index: FrameIndex,
        *,
        clip_id: str,
        video_path: Path,
        draft_path: Path,
        annotation_path: Path,
    ) -> None:
        self.frame_index = frame_index
        self.clip_id = clip_id
        self.video_path = video_path
        self.draft_path = draft_path
        self.annotation_path = annotation_path
        self._events: list[dict[str, object]] = []
        self._undo: list[list[dict[str, object]]] = []
        self._lock = threading.RLock()
        self._restore()

    def _next_id(self) -> str:
        used = {str(event["id"]) for event in self._events}
        number = 1
        while f"ev_{number:03d}" in used:
            number += 1
        return f"ev_{number:03d}"

    def _derive_event(self, raw: Mapping[str, Any], *, event_id: str) -> dict[str, object]:
        start_value = raw["frame_start"]
        end_value = raw["frame_end"]
        if (
            isinstance(start_value, bool)
            or not isinstance(start_value, int)
            or isinstance(end_value, bool)
            or not isinstance(end_value, int)
        ):
            raise AnnotatorError("frame_start and frame_end must be integers")
        start = start_value
        end = end_value
        start_record = self.frame_index.record(start)
        end_record = self.frame_index.record(end)
        candidate = {
            "id": event_id,
            "type": raw.get("type", "unknown"),
            "frame_start": start,
            "frame_end": end,
            "frame_range": [start, end],
            "time_start_seconds": start_record.timestamp_seconds,
            "time_end_seconds": end_record.timestamp_seconds,
            "player": raw.get("player", "unknown"),
            "side": raw.get("side", "unknown"),
            "shot_type": raw.get("shot_type", "unknown"),
            "court_zone": raw.get("court_zone", "unknown"),
            "source": "manual_annotation",
            "notes": raw.get("notes", ""),
        }
        normalize_narrative_event(candidate)
        return candidate

    def _snapshot(self) -> list[dict[str, object]]:
        return json.loads(json.dumps(self._events))

    def _remember(self) -> None:
        self._undo.append(self._snapshot())
        self._undo = self._undo[-50:]

    def _annotation_payload(self) -> dict[str, object]:
        return {
            "clip_id": self.clip_id,
            "clip_path": str(self.video_path),
            "level": "A2",
            "fps": 60.0,
            "timing_mode": "variable_frame_rate",
            "duration_seconds": self.frame_index.duration_seconds,
            "frames_total": self.frame_index.frame_count,
            "video_sha256": self.frame_index.video_sha256,
            "narrative_events": self._snapshot(),
            "ball_manual_positions": [],
            "notes": "Eventos creados y revisados manualmente con event_annotator_app.",
        }

    def _write_atomic(self, path: Path, payload: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)

    def _autosave(self) -> None:
        self._write_atomic(self.draft_path, self._annotation_payload())

    def _restore(self) -> None:
        if not self.draft_path.is_file():
            return
        payload = json.loads(self.draft_path.read_text(encoding="utf-8"))
        raw_events = payload.get("narrative_events", [])
        if not isinstance(raw_events, list):
            raise AnnotatorError("Draft narrative_events must be a list")
        restored: list[dict[str, object]] = []
        for raw in raw_events:
            restored.append(self._derive_event(raw, event_id=str(raw["id"])))
        if len({event["id"] for event in restored}) != len(restored):
            raise AnnotatorError("Draft contains duplicate event IDs")
        self._events = sorted(
            restored, key=lambda event: (event["frame_start"], event["frame_end"])
        )

    def list(self) -> list[dict[str, object]]:
        with self._lock:
            return self._snapshot()

    def create(self, raw: Mapping[str, Any]) -> dict[str, object]:
        with self._lock:
            preset_name = raw.get("preset")
            values = dict(PRESETS.get(str(preset_name), {})) if preset_name is not None else {}
            if preset_name is not None and not values:
                raise AnnotatorError(f"Unknown event preset: {preset_name}")
            values.update({key: value for key, value in raw.items() if key != "preset"})
            if "frame_start" not in values or "frame_end" not in values:
                raise AnnotatorError("frame_start and frame_end are required")
            self._remember()
            event = self._derive_event(values, event_id=self._next_id())
            self._events.append(event)
            self._events.sort(key=lambda item: (item["frame_start"], item["frame_end"]))
            self._autosave()
            return json.loads(json.dumps(event))

    def update(self, event_id: str, changes: Mapping[str, Any]) -> dict[str, object]:
        with self._lock:
            index = next(
                (i for i, event in enumerate(self._events) if event["id"] == event_id), None
            )
            if index is None:
                raise AnnotatorError(f"Unknown event ID: {event_id}")
            allowed = {
                "type",
                "player",
                "side",
                "shot_type",
                "court_zone",
                "notes",
                "frame_start",
                "frame_end",
            }
            unexpected = set(changes).difference(allowed)
            if unexpected:
                raise AnnotatorError(f"Unsupported event fields: {', '.join(sorted(unexpected))}")
            self._remember()
            merged = {**self._events[index], **changes}
            updated = self._derive_event(merged, event_id=event_id)
            self._events[index] = updated
            self._events.sort(key=lambda item: (item["frame_start"], item["frame_end"]))
            self._autosave()
            return json.loads(json.dumps(updated))

    def delete(self, event_id: str) -> None:
        with self._lock:
            index = next(
                (i for i, event in enumerate(self._events) if event["id"] == event_id), None
            )
            if index is None:
                raise AnnotatorError(f"Unknown event ID: {event_id}")
            self._remember()
            self._events.pop(index)
            self._autosave()

    def undo(self) -> list[dict[str, object]]:
        with self._lock:
            if not self._undo:
                raise AnnotatorError("Nothing to undo")
            self._events = self._undo.pop()
            self._autosave()
            return self.list()

    def export(self) -> Path:
        with self._lock:
            if not self._events:
                raise AnnotatorError("Cannot export without human events")
            payload = self._annotation_payload()
            normalize_annotation(payload)
            self._write_atomic(self.annotation_path, payload)
            return self.annotation_path


class AnnotatorSession:
    """Prepared video, exact index, optional tracking, event store, and readiness gate."""

    def __init__(
        self,
        config: SessionConfig,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config.resolved()
        self._input_hashes = self._hash_inputs()
        self.frame_index, self.manifest, self.sidecar = build_frame_index(
            self.config,
            progress=progress,
        )
        self.tracking = load_tracking(self.config.tracking_path, self.frame_index.frame_count)
        if self.config.draft_path is None or self.config.annotation_path is None:
            raise AnnotatorError("Session output paths are unresolved")
        self.events = EventStore(
            self.frame_index,
            clip_id=self.config.clip_id,
            video_path=self.config.video_path,
            draft_path=self.config.draft_path,
            annotation_path=self.config.annotation_path,
        )
        self.self_test = run_self_test(self)
        self.ready = bool(self.self_test["passed"])

    def _hash_inputs(self) -> dict[str, str]:
        paths = [self.config.video_path, self.config.manifest_path, self.config.timestamps_path]
        if self.config.tracking_path is not None and self.config.tracking_path.is_file():
            paths.append(self.config.tracking_path)
        return {
            str(path): sha256_file(path) for path in paths if path is not None and path.is_file()
        }

    def input_hashes_unchanged(self) -> bool:
        return self._input_hashes == self._hash_inputs()

    def session_payload(self) -> dict[str, object]:
        return {
            "clip_id": self.config.clip_id,
            "frame_count": self.frame_index.frame_count,
            "first_frame_id": 0,
            "last_frame_id": self.frame_index.frame_count - 1,
            "width": self.frame_index.width,
            "height": self.frame_index.height,
            "duration_seconds": self.frame_index.duration_seconds,
            "ready": self.ready,
            "self_test_status": self.self_test["status"],
            "tracking_available": bool(self.tracking),
            "draft_restored": bool(self.events.list()),
            "frame_timestamps": [record.timestamp_seconds for record in self.frame_index.records],
        }

    def frame_metadata(self, frame_id: int) -> dict[str, object]:
        record = self.frame_index.record(frame_id)
        return {**asdict(record), "tracking": self.tracking.get(frame_id)}


def _self_test_result(number: int, name: str, check: Callable[[], Any]) -> dict[str, object]:
    try:
        detail = check()
        return {"id": number, "name": name, "passed": True, "detail": detail or "OK"}
    except Exception as exc:  # The endpoint must report every failed criterion.
        return {"id": number, "name": name, "passed": False, "detail": str(exc)}


def run_self_test(session: AnnotatorSession) -> dict[str, object]:
    """Execute the mandatory 30-point readiness gate without touching real annotations."""
    index = session.frame_index
    manifest = session.manifest
    sidecar = session.sidecar
    results: list[dict[str, object]] = []

    def add(name: str, check: Callable[[], Any]) -> None:
        results.append(_self_test_result(len(results) + 1, name, check))

    def require(condition: bool, detail: str) -> str:
        if not condition:
            raise AnnotatorError(detail)
        return detail

    add("Video encontrado", lambda: require(session.config.video_path.is_file(), "video found"))
    add(
        "SHA calculado",
        lambda: require(index.video_sha256 == manifest.source_sha256, index.video_sha256),
    )
    add(
        "Manifest cargado",
        lambda: require(manifest.clip_id == session.config.clip_id, manifest.clip_id),
    )
    add("527 timestamps", lambda: require(len(sidecar.frames) == 527, "527 timestamps"))
    add(
        "Timestamps estrictamente crecientes",
        lambda: require(
            all(
                b.timestamp_seconds > a.timestamp_seconds
                for a, b in zip(sidecar.frames, sidecar.frames[1:])
            ),
            "strict timestamps",
        ),
    )
    add("527 frames decodificados", lambda: require(index.frame_count == 527, "527 cached frames"))
    add(
        "IDs exactamente 0–526",
        lambda: require([r.frame_id for r in index.records] == list(range(527)), "0–526"),
    )
    add(
        "Sin IDs duplicados",
        lambda: require(len({r.frame_id for r in index.records}) == 527, "unique IDs"),
    )
    add(
        "Sin IDs faltantes",
        lambda: require(
            set(r.frame_id for r in index.records) == set(range(527)), "no missing IDs"
        ),
    )
    add(
        "Resolución 2746×1536",
        lambda: require((index.width, index.height) == (2746, 1536), "2746x1536"),
    )

    def readable(frame_id: int) -> str:
        image = cv2.imread(str(index.image_path(frame_id)))
        return require(
            image is not None and image.shape[:2] == (1536, 2746), f"frame {frame_id} readable"
        )

    for frame_id in (0, 1, 2, 526):
        add(f"Frame {frame_id} legible", lambda value=frame_id: readable(value))
    add(
        "Ruta frame 11 distinta de 12",
        lambda: require(index.image_path(11) != index.image_path(12), "11 != 12"),
    )
    add(
        "Ruta frame 12 distinta de 13",
        lambda: require(index.image_path(12) != index.image_path(13), "12 != 13"),
    )

    def navigation(start: int, deltas: list[int], expected: list[int]) -> str:
        navigator = NavigationState(index, start)
        actual = [navigator.current]
        for delta in deltas:
            actual.append(navigator.move(delta))
        require(actual == expected, f"expected {expected}, got {actual}")
        for frame_id in actual:
            require(
                index.image_path(frame_id).name == f"frame_{frame_id:06d}.webp",
                "cache path mismatch",
            )
        return "→".join(map(str, actual))

    add("Navegación 0→1→2→1", lambda: navigation(0, [1, 1, -1], [0, 1, 2, 1]))
    add(
        "Navegación 10→11→12→13→12→11→10",
        lambda: navigation(10, [1, 1, 1, -1, -1, -1], [10, 11, 12, 13, 12, 11, 10]),
    )
    add("Salto 0→100", lambda: require(NavigationState(index).jump(100) == 100, "0→100"))
    add("Salto 100→526", lambda: require(NavigationState(index, 100).jump(526) == 526, "100→526"))

    def bounds_rejected() -> str:
        for value in (-1, 527):
            try:
                index.record(value)
            except AnnotatorError:
                continue
            raise AnnotatorError(f"bound {value} was accepted")
        return "-1 and 527 rejected"

    add("Bounds -1 y 527 rechazados", bounds_rejected)

    with tempfile.TemporaryDirectory(prefix="annotator_self_test_") as directory:
        temporary = Path(directory)
        store = EventStore(
            index,
            clip_id=session.config.clip_id,
            video_path=session.config.video_path,
            draft_path=temporary / "draft.json",
            annotation_path=temporary / "manual_annotation.json",
        )
        event_one: dict[str, object] = {}
        event_range: dict[str, object] = {}

        def create_one() -> str:
            event_one.update(
                store.create({"preset": "hit_near", "frame_start": 100, "frame_end": 100})
            )
            return require(
                event_one["frame_start"] == event_one["frame_end"] == 100, "single frame"
            )

        def create_range() -> str:
            event_range.update(
                store.create({"preset": "hit_far", "frame_start": 132, "frame_end": 134})
            )
            return require(
                (event_range["frame_start"], event_range["frame_end"]) == (132, 134), "132–134"
            )

        add("Evento de un frame válido", create_one)
        add("Evento de rango 132–134 válido", create_range)
        add(
            "Timestamps del rango derivados correctamente",
            lambda: require(
                event_range["time_start_seconds"] == index.record(132).timestamp_seconds
                and event_range["time_end_seconds"] == index.record(134).timestamp_seconds,
                "timestamps derived from index",
            ),
        )
        add(
            "Autosave válido",
            lambda: require(
                json.loads((temporary / "draft.json").read_text())["narrative_events"],
                "draft saved",
            ),
        )

        def undo_valid() -> str:
            restored = store.undo()
            return require(
                len(restored) == 1 and restored[0]["frame_start"] == 100, "undo restored snapshot"
            )

        add("Undo válido", undo_valid)
        add(
            "Reload del borrador válido",
            lambda: require(
                len(
                    EventStore(
                        index,
                        clip_id=session.config.clip_id,
                        video_path=session.config.video_path,
                        draft_path=temporary / "draft.json",
                        annotation_path=temporary / "manual_annotation.json",
                    ).list()
                )
                == 1,
                "draft restored",
            ),
        )
        add("Export fixture válido", lambda: require(store.export().is_file(), "fixture exported"))
        add(
            "event_loader acepta la fixture",
            lambda: require(
                len(load_normalized_events(temporary / "manual_annotation.json")[1]) == 1,
                "event_loader accepted fixture",
            ),
        )
    add(
        "Ningún input original modificado",
        lambda: require(session.input_hashes_unchanged(), "input hashes unchanged"),
    )

    passed_count = sum(bool(result["passed"]) for result in results)
    passed = passed_count == 30 and len(results) == 30
    return {
        "status": "PASSED_30_30" if passed else f"FAILED_{passed_count}_OF_30",
        "passed": passed,
        "passed_count": passed_count,
        "total": 30,
        "criteria": results,
    }
