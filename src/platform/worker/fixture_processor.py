from __future__ import annotations

import json
import time
from hashlib import sha256

from .protocol import AnalysisContext, AnalysisResult


class ContractFixtureProcessor:
    """Small deterministic processor used by local/CI runtime evidence.

    It writes only JSON contract fixtures.  FAST intentionally exercises the
    partial terminal path and TACTICAL exercises the public failure path; no
    profile performs video work or inference.
    """

    def process(self, context: AnalysisContext) -> AnalysisResult:
        for _ in range(3):
            if context.cancelled():
                return AnalysisResult("CANCELLED", error_code="ANALYSIS_CANCELLED")
            time.sleep(0.01)
        if context.processing_profile == "TACTICAL":
            return AnalysisResult("FAILED", error_code="ANALYSIS_INPUT_INVALID")
        status = "PARTIAL" if context.processing_profile == "FAST" else "COMPLETE"
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
        return AnalysisResult(status, (manifest, metrics), result_manifest="manifest.json")
