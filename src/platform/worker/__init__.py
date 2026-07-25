"""Stage 2C worker runtime.

The worker package deliberately contains only orchestration and a deterministic
contract fixture.  Vision processing is an explicit future processor seam.
"""

from .protocol import AnalysisContext, AnalysisProcessor, AnalysisResult
from .runtime import WorkerRuntime

__all__ = ["AnalysisContext", "AnalysisProcessor", "AnalysisResult", "WorkerRuntime"]
