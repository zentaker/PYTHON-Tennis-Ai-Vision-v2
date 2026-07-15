# Guía histórica de anotación manual — Stage 4 Nivel A

> **Retirada para Nivel A2.** La herramienta estática descrita en este documento no es
> ejecutable y no debe abrirse. No garantizaba navegación frame-accurate.

Para `nivel_a2_01`, usar exclusivamente la guía actual:
`docs/levels/level_a2/stage_4_annotation_guide.md`.

El resto de este documento conserva el contexto histórico del clip Madrid; no es una
instrucción operativa para A2.

## Objetivo

Crear `data/reference_clip/manual_annotation.json` a partir de observacion humana del
rally. La herramienta no analiza el video ni propone eventos.

## Procedimiento histórico

El flujo anterior dependía de selección manual de archivos y FPS nominal. Queda
documentado únicamente para explicar por qué fue reemplazado; no debe utilizarse.

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
