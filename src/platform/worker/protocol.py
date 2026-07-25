from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Event
from typing import Protocol
from uuid import UUID

from ..domain.enums import ArtifactKind


class ProcessorOutcome(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True)
class ProcessorArtifact:
    relative_path: str
    kind: ArtifactKind
    media_type: str
    schema_version: str


@dataclass(frozen=True)
class AnalysisContext:
    """Immutable run inputs exposed to a processor.

    ``workspace`` is a private per-attempt directory.  A processor must not
    write outside it, call a vision model, or publish directly to storage.
    """

    run_id: UUID
    session_id: UUID
    input_video_id: UUID | None
    processing_profile: str
    attempt: int
    workspace: Path
    cancellation_requested: Event
    shutdown_requested: Event

    def cancelled(self) -> bool:
        return self.cancellation_requested.is_set()

    def stopped(self) -> bool:
        return self.cancellation_requested.is_set() or self.shutdown_requested.is_set()


@dataclass(frozen=True)
class AnalysisResult:
    """Processor output; publication and state transitions remain runtime-owned."""

    status: ProcessorOutcome | str
    artifacts: tuple[ProcessorArtifact, ...] = ()
    error_code: str | None = None
    bundle_fingerprint: str | None = None
    result_manifest: str | None = None


class AnalysisProcessor(Protocol):
    def process(self, context: AnalysisContext) -> AnalysisResult: ...
