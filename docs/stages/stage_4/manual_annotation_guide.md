# Guia de anotacion manual - Stage 4 Nivel A

## Objetivo

Crear `data/reference_clip/manual_annotation.json` a partir de observacion humana del
rally. La herramienta no analiza el video ni propone eventos.

## Abrir la herramienta

Abrir directamente en un navegador:

```text
tools/manual_event_annotator/index.html
```

No requiere servidor, CDN, OpenCV ni conexion a Internet.

## Procedimiento

1. Seleccionar `madrid_R1.mov` desde el control de archivo.
2. Confirmar FPS; el valor esperado del run anterior es 60.
3. Reproducir, pausar o usar los botones/teclas de avance frame a frame.
4. Para cada evento humano, capturar frame inicial y final.
5. Seleccionar tipo, player, side, shot type y court zone.
6. Guardar. Los eventos pueden editarse o eliminarse y se muestran cronologicamente.
7. Revisar la tabla completa antes de exportar.
8. Exportar `manual_annotation.json` y moverlo a `data/reference_clip/`.

## Vocabularios

- `type`: `serve`, `hit`, `bounce`, `unknown`.
- `player` y `side`: `near`, `far`, `unknown`.
- `shot_type`: `saque`, `derecha`, `revés`, `derecha_invertida`,
  `revés_invertido`, `slice`, `volea`, `dejada`, `globo`, `unknown`.
- `court_zone`: `zona_saque_derecha`, `zona_saque_izquierda`, `fondo`, `media`,
  `aprox_red`, `red`, `unknown`.

Usar `unknown` cuando el video o el conocimiento de dominio no permitan decidir. No
adivinar una clasificacion para evitar `unknown`.

## Validar y normalizar

```bash
uv run python -m src.events.event_loader \
  --annotation data/reference_clip/manual_annotation.json \
  --output outputs/stage_4/events.json
```

El loader rechaza listas vacias, IDs duplicados, rangos invalidos, eventos desordenados,
vocabularios no permitidos y frames fuera de `frames_total`.

Las fixtures de `tests/fixtures/` son sinteticas y solo prueban el codigo. Nunca deben
usarse como anotacion del rally real.
