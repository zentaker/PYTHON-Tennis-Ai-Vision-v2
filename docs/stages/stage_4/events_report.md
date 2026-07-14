# Events Report - Stage 4 Nivel A

**Estado:** Implementacion validada con fixtures; run real pendiente
**Fecha:** 2026-07-13

## Alcance validado

La base ligera de Stage 4 normaliza eventos manuales, valida vocabularios, rangos, FPS,
orden cronologico, IDs y bounds opcionales de `frames_total`. La exportacion vacia esta
bloqueada para impedir que el pipeline invente evidencia.

Los tests usan exclusivamente JSON sintetico bajo `tests/fixtures/`. No representan el
rally Madrid R1 y no se copiaron a `data/` ni a `outputs/`.

## Implementacion

- `src/events/event_schema.py`
- `src/events/event_loader.py`
- `src/events/render_events_overlay.py`
- `src/events/render_events_timeline.py`
- `tools/manual_event_annotator/index.html`
- `tests/test_event_schema.py`
- `tests/test_event_loader.py`

## Evidencia automatica

Los tests especificos cubren:

- JSON valido e invalido;
- vocabularios permitidos;
- conversion de `frame_range`;
- calculo de segundos con FPS configurable;
- preservacion y validacion del orden cronologico;
- rechazo de lista vacia y de eventos fuera de bounds;
- export de `events.json` despues de validar.

## Artefactos reales

No se genero:

```text
outputs/stage_4/events.json
outputs/stage_4/events_timeline.png
outputs/stage_4/events_overlay.mp4
```

La ausencia es intencional: faltan el video, la trayectoria suavizada y la anotacion
humana. Generar archivos con fixtures en esas rutas produciria evidencia falsa.

## Gate

Pendiente. Este reporte debe completarse con conteo de eventos, FPS, rutas de artefactos
y veredicto humano despues de ejecutar el pipeline con `manual_annotation.json` real.
