from pathlib import Path


ANNOTATOR = Path("tools/manual_event_annotator/index.html")


def test_a2_annotator_uses_real_vfr_sidecar_and_exports_explicit_coordinates() -> None:
    html = ANNOTATOR.read_text(encoding="utf-8")

    assert 'id="timestampsFile"' in html
    assert "payload.frames.length !== 527" in html
    assert "frameTimeline[middle].timestamp_seconds" in html
    assert "video.currentTime = timeForFrame(target)" in html
    assert "video.currentTime * fps()" not in html
    assert "frame_start: start" in html
    assert "frame_end: end" in html
    assert "time_start_seconds: timeForFrame(start)" in html
    assert "time_end_seconds: timeForFrame(end)" in html
    assert 'clip_id: "nivel_a2_01"' in html
    assert 'level: "A2"' in html
    assert 'timing_mode: "variable_frame_rate"' in html


def test_a2_annotator_refuses_event_creation_and_export_without_sidecar() -> None:
    html = ANNOTATOR.read_text(encoding="utf-8")

    assert "Cargá frame_timestamps.json antes de guardar." in html
    assert "Cargá el sidecar VFR antes de exportar A2." in html
