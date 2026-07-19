"""Reconcile contact ball pixels without event-specific decisions."""

from __future__ import annotations

from typing import Any

import numpy as np


def reconcile_contact_pixel(
    *,
    raw_pixel: tuple[float, float] | None,
    smoothed_pixel: tuple[float, float] | None,
    p1_pixel: tuple[float, float] | None,
    raw_confidence: float,
    smoothed_confidence: float,
    p1_confidence: float,
    raw_outlier: bool,
    inconsistency_threshold_px: float = 80.0,
) -> dict[str, Any]:
    sources = {
        "raw": raw_pixel,
        "smoothed": smoothed_pixel,
        "p1_contact": p1_pixel,
    }
    valid = {name: np.asarray(pixel, dtype=float) for name, pixel in sources.items() if pixel}
    if not valid:
        raise ValueError("no contact ball pixel source")
    pairwise = {
        f"{left}_to_{right}": float(np.linalg.norm(valid[left] - valid[right]))
        for index, left in enumerate(valid)
        for right in list(valid)[index + 1 :]
    }
    inconsistent = max(pairwise.values(), default=0.0) > inconsistency_threshold_px
    if raw_pixel is not None and raw_confidence >= 0.5 and not raw_outlier:
        selected_name = "raw"
    elif p1_pixel is not None and p1_confidence >= smoothed_confidence:
        selected_name = "p1_contact"
    else:
        selected_name = "smoothed"
    selected = valid[selected_name]
    spread = np.vstack(list(valid.values())) - selected
    covariance = np.cov(spread.T).tolist() if len(valid) > 1 else [[9.0, 0.0], [0.0, 9.0]]
    if inconsistent:
        covariance = (np.asarray(covariance) + np.eye(2) * max(pairwise.values()) ** 2 / 4).tolist()
    return {
        "smoothed_pixel": list(smoothed_pixel) if smoothed_pixel else None,
        "raw_pixel": list(raw_pixel) if raw_pixel else None,
        "p1_contact_pixel": list(p1_pixel) if p1_pixel else None,
        "interpolation_status": "interpolated" if raw_pixel is None else "raw_available",
        "pairwise_pixel_distances": pairwise,
        "confidence_by_source": {
            "raw": raw_confidence,
            "smoothed": smoothed_confidence,
            "p1_contact": p1_confidence,
        },
        "selected_canonical_ball_pixel": selected.tolist(),
        "canonical_pixel_covariance": covariance,
        "selection_reason": f"general_priority_rule:{selected_name}",
        "status": "CONTACT_PIXEL_INCONSISTENT" if inconsistent else "CONTACT_PIXEL_RECONCILED",
        "warnings": ["CONTACT_PIXEL_INCONSISTENT"] if inconsistent else [],
    }
