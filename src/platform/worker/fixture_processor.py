from __future__ import annotations

import json
import time
from hashlib import sha256

from ..domain.enums import ArtifactKind
from .protocol import AnalysisContext, AnalysisResult, ProcessorArtifact, ProcessorOutcome


class ContractFixtureProcessor:
    """Small deterministic processor used by local/CI runtime evidence.

    It writes only JSON contract fixtures.  FAST intentionally exercises the
    partial terminal path and TACTICAL exercises the public failure path; no
    profile performs video work or inference.
    """

    def process(self, context: AnalysisContext) -> AnalysisResult:
        for _ in range(3):
            if context.stopped():
                return AnalysisResult(ProcessorOutcome.CANCELLED, error_code="ANALYSIS_CANCELLED")
            time.sleep(0.01)
        if context.processing_profile == "TACTICAL":
            return AnalysisResult(ProcessorOutcome.FAILED, error_code="ANALYSIS_INPUT_INVALID")
        status = ProcessorOutcome.PARTIAL if context.processing_profile == "FAST" else ProcessorOutcome.COMPLETE
        manifest = context.workspace / "manifest.json"
        metrics = context.workspace / "metrics.json"
        metrics.write_text(
            json.dumps(
                {
                    "schema_version": "stage2c.fixture.v1",
                    "run_id": str(context.run_id),
                    "attempt": context.attempt,
                    "status": status,
                    "inference": False,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        digest = sha256(metrics.read_bytes()).hexdigest()
        manifest.write_text(
            json.dumps(
                {"schema_version": "stage2c.fixture.v1", "metrics_sha256": digest},
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return AnalysisResult(
            status,
            (
                ProcessorArtifact("manifest.json", ArtifactKind.MANIFEST, "application/json", "stage2c.fixture.v1"),
                ProcessorArtifact("metrics.json", ArtifactKind.METRICS, "application/json", "stage2c.fixture.v1"),
            ),
            result_manifest="manifest.json",
        )
