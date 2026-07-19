from __future__ import annotations

from src.stage5b_v3.contact_pixel_reconciliation import reconcile_contact_pixel


def test_raw_smoothed_and_p1_reconciliation() -> None:
    result = reconcile_contact_pixel(
        raw_pixel=(10, 10),
        smoothed_pixel=(12, 11),
        p1_pixel=(11, 10),
        raw_confidence=0.9,
        smoothed_confidence=0.8,
        p1_confidence=0.7,
        raw_outlier=False,
    )
    assert result["selected_canonical_ball_pixel"] == [10, 10]
    assert result["status"] == "CONTACT_PIXEL_RECONCILED"
    assert len(result["pairwise_pixel_distances"]) == 3


def test_conflicting_pixels_expand_uncertainty() -> None:
    result = reconcile_contact_pixel(
        raw_pixel=(0, 0),
        smoothed_pixel=(200, 0),
        p1_pixel=(0, 200),
        raw_confidence=0.9,
        smoothed_confidence=0.8,
        p1_confidence=0.7,
        raw_outlier=False,
    )
    assert result["status"] == "CONTACT_PIXEL_INCONSISTENT"
    assert result["canonical_pixel_covariance"][0][0] > 1000


def test_outlier_raw_does_not_win() -> None:
    result = reconcile_contact_pixel(
        raw_pixel=(0, 0),
        smoothed_pixel=(10, 10),
        p1_pixel=(11, 10),
        raw_confidence=0.99,
        smoothed_confidence=0.8,
        p1_confidence=0.9,
        raw_outlier=True,
    )
    assert result["selected_canonical_ball_pixel"] == [11, 10]
