"""Isolated Stage 5A.1 tool contracts (no video decoding or human clicks)."""

import numpy as np

from tools.vertical_reference_app.core import (
    HEIGHT,
    WIDTH,
    VerticalReferenceSession,
    canvas_to_image_point,
)


def test_canvas_mapping_contains_zoom_pan_and_canonical_corners() -> None:
    assert canvas_to_image_point((0, 0), (WIDTH, HEIGHT), 1, (0, 0)) == (0.0, 0.0)
    assert canvas_to_image_point((WIDTH, HEIGHT), (WIDTH, HEIGHT), 1, (0, 0)) == (WIDTH, HEIGHT)
    assert np.allclose(
        canvas_to_image_point((WIDTH / 2, HEIGHT / 2), (WIDTH, HEIGHT), 2, (100, 30)),
        [(WIDTH - 100) / 2, (HEIGHT - 30) / 2],
    )


def test_self_test_passes_without_gpu_or_event_annotator_state() -> None:
    session = VerticalReferenceSession("nivel_a2_01")
    assert session.self_test["status"] == "PASS"
    assert session.self_test["core_self_test"] == "PASS"
    assert session.self_test["browser_e2e_test"] == "RUN_SEPARATELY"
    assert session.self_test["check_count"] == 28
    assert session.self_test["checks"]["stage5b_not_started"]
    assert session.self_test["checks"]["event_annotator_isolated"]


def test_post_classification_uses_regulation_geometry() -> None:
    session = VerticalReferenceSession("nivel_a2_01")
    H = np.asarray(session.homography["H_court_to_pixel"], dtype=np.float64)
    world = np.array([[-5.485, 0.0, 1.0]], dtype=np.float64)
    pixel_h = (H @ np.r_[world[0, :2], 1.0])
    pixel = tuple((pixel_h[:2] / pixel_h[2]).tolist())
    candidate = session.classify_post(pixel)
    assert candidate is not None
    assert candidate.side == "left"
