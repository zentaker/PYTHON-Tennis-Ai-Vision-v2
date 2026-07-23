"""Optional local Session Platform foundation.

This package intentionally keeps optional infrastructure imports lazy. Importing
``src.platform`` never imports models, OpenCV, torch or tracking code.
"""

SESSION_PLATFORM_API_STYLE = "LAYERED_FASTAPI_COMPATIBLE_WITH_EXISTING_EXPRESS_MENTAL_MODEL"

__all__ = ["SESSION_PLATFORM_API_STYLE"]
