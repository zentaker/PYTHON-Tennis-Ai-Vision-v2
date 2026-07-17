"""Lazy OpenMMLab adapter boundary; no imports or downloads at module import."""

from __future__ import annotations


class OpenMMLabBackend:
    name = "openmmlab"

    def __init__(self, config_path=None, device: str = "auto"):
        self.config_path = config_path
        self.device = device
        try:
            import importlib.util

            available = importlib.util.find_spec("mmdet") and importlib.util.find_spec("mmpose")
        except (ImportError, ModuleNotFoundError):
            available = False
        if not available:
            raise RuntimeError(
                "OpenMMLab extras are not installed; install the portable GPU environment before selecting this backend"
            )

    def process(self, frame_id, image):
        raise NotImplementedError(
            "Real OpenMMLab inference is intentionally not run in P1 preparation"
        )
