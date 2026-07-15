# Events Report - Stage 4 Nivel A

**Estado:** Anotador A2 verificado; anotación humana y run real pendientes
**Fecha:** 2026-07-15

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
- `tools/event_annotator_app/` — aplicación local activa y frame-accurate
- `tools/manual_event_annotator/index.html` — retirada, no ejecutable
- `tests/test_event_annotator_app.py`
- `tests/test_event_schema.py`
- `tests/test_event_loader.py`

## Evidencia automatica

El anotador A2 pasó `PASSED_30_30` con el video canónico: 527 frames, IDs consecutivos
`0–526`, timestamps estrictos, resolución `2746×1536`, navegación exacta y evento de
rango `132–134`. La prueba HTTP aislada también confirmó autosave, undo, restart,
restore, delete y limpieza sin escribir anotaciones reales.

La documentación de diseño y aceptación está en
`docs/levels/level_a2/stage_4_annotator_redesign.md`.

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

La ausencia es intencional: todavía falta la anotación humana real. Generar esos
artefactos con fixtures produciría evidencia falsa.

## Gate

Pendiente. Este reporte debe completarse con conteo de eventos, rutas de artefactos y
veredicto humano después de ejecutar el pipeline con `manual_annotation.json` real.
