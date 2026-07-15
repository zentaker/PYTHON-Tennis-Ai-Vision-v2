from pathlib import Path


LEGACY = Path("tools/manual_event_annotator/index.html")
FRONTEND = Path("tools/event_annotator_app/static/index.html")
JAVASCRIPT = Path("tools/event_annotator_app/static/app.js")


def test_rejected_annotator_is_deprecated_and_not_executable() -> None:
    html = LEGACY.read_text(encoding="utf-8")

    assert "Herramienta retirada" in html
    assert "deprecado" in html
    assert 'type="file"' not in html
    assert "HTMLVideoElement" not in html


def test_verified_frontend_hides_technical_file_controls() -> None:
    html = FRONTEND.read_text(encoding="utf-8")

    assert "Anotador de eventos de tenis" in html
    assert 'type="file"' not in html
    assert "frame_timestamps" not in html
    assert "Sidecar" not in html
    assert "FPS" not in html
    assert "Manifest" not in html
    assert "SHA" not in html
    assert "FRAME 000 / 526" in html
    assert "Marcar inicio" in html
    assert "Marcar fin" in html
    assert "Finalizar y guardar anotación" in html


def test_frontend_navigation_uses_exact_cached_frame_endpoints() -> None:
    javascript = JAVASCRIPT.read_text(encoding="utf-8")

    assert "HTMLVideoElement" not in javascript
    assert "currentTime" not in javascript
    assert "* fps" not in javascript
    assert "function frameUrl(frameId) { return `/api/frames/${frameId}`; }" in javascript
    assert "state.current + Number(button.dataset.nav)" in javascript
    assert "if (state.loading || !state.session) return false" in javascript
    assert "for (let offset = -10; offset <= 10; offset += 1)" in javascript
