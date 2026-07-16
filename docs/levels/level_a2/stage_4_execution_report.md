# Stage 4 A2 — Reporte de ejecución

**Estado:** `CLOSED_SUCCESSFULLY`

**Fecha:** 2026-07-16

**Commit inicial de esta corrección:** `dbc1323da0279d75c8157171240c79223ebba374`

## Corrección confirmada

La primera ejecución tenía nueve eventos. El usuario detectó un bote terminal omitido,
lo añadió en el anotador frame-accurate y pulsó nuevamente **Finalizar y guardar
anotación**. La persistencia actual contiene diez eventos y el nuevo `ev_010` fue usado
como fuente canónica; no se reconstruyeron ni editaron silenciosamente los nueve
anteriores.

## Persistencia y backups

Final, borrador y `GET /api/events` contienen 10 eventos concordantes. El endpoint de
sesión sigue listo (`PASSED_30_30`, `draft_restored=true`).

| Evidencia | Estado | Tamaño | Eventos | SHA-256 |
| --- | --- | ---: | ---: | --- |
| Archivo final | JSON válido | 4485 B | 10 | `9d7668eef478a85f9d8d1146058c19dafe975466119a271e03f9925ae58a7e8b` |
| Borrador | JSON válido | 4485 B | 10 | `9d7668eef478a85f9d8d1146058c19dafe975466119a271e03f9925ae58a7e8b` |
| `GET /api/events` | Respuesta válida | — | 10 | — |

SHA anterior de la anotación de nueve eventos:
`1e540abe1ef3545969d84d07763c132adcf851788e6fe51a14999a4a3cda0e84`.

Backups nuevos, creados antes de normalizar:

- `outputs/nivel_a2_01/stage_4/backups/manual_annotation_with_terminal_bounce_20260716T112527-0500.json`;
- `outputs/nivel_a2_01/stage_4/backups/annotation_draft_with_terminal_bounce_20260716T112527-0500.json`.

Ambos coinciden byte a byte con final y borrador, con SHA
`9d7668eef478a85f9d8d1146058c19dafe975466119a271e03f9925ae58a7e8b`. Los backups de
nueve eventos anteriores se conservaron.

## Auditoría de los diez eventos

Los nueve eventos anteriores son byte-semánticamente equivalentes al backup anterior en
ID, tipo, jugador, lado, rangos, timestamps, subtipo, zona, fuente y notas.

El décimo evento coincide con la captura humana actual y con el índice VFR:

| Campo | `ev_010` |
| --- | --- |
| Tipo | `bounce` |
| Jugador/lado | `unknown/far` |
| Frames | `463–463` |
| Cantidad | `1` |
| Timestamp | `9.221667–9.221667 s` |
| `shot_type` / `court_zone` | `unknown` / `unknown` |
| `source` | `manual_annotation` |
| `notes` | vacío, conservado del archivo guardado |

Frame 463 en `frame_timestamps.json` tiene timestamp `9.221667` y el error guardado es
`0.0 s`.

| ID | Tipo | Jugador | Lado | Frames | Cantidad | Timestamps (s) |
| --- | --- | --- | --- | --- | ---: | --- |
| ev_001 | serve | near | near | 139–139 | 1 | 2.771667–2.771667 |
| ev_002 | bounce | unknown | far | 158–158 | 1 | 3.138333–3.138333 |
| ev_003 | hit | far | far | 200–200 | 1 | 3.955000–3.955000 |
| ev_004 | bounce | unknown | near | 262–264 | 3 | 5.188333–5.238333 |
| ev_005 | hit | near | near | 287–288 | 2 | 5.688333–5.721667 |
| ev_006 | bounce | unknown | far | 327–327 | 1 | 6.488333–6.488333 |
| ev_007 | hit | far | far | 351–351 | 1 | 6.971667–6.971667 |
| ev_008 | bounce | unknown | near | 399–400 | 2 | 7.938333–7.955000 |
| ev_009 | hit | near | near | 434–435 | 2 | 8.638333–8.655000 |
| ev_010 | bounce | unknown | far | 463–463 | 1 | 9.221667–9.221667 |

Conteos: `serve=1`, `hit=4`, `bounce=5`; eventos puntuales `6`; multiframe `4`;
jugador `near=3`, `far=2`, `unknown=5`; lado `near=5`, `far=5`.

## Normalización y outputs

El loader A2 se ejecutó con el video canónico, manifest, `frame_timestamps.json` y el
archivo final. Registró `clip_id=nivel_a2_01`, `frames_total=527` y
`timing_mode=variable_frame_rate`, sin modificar `manual_annotation.json`.

### Overlay completo

[events_overlay.mp4](/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/nivel_a2_01/stage_4/events_overlay.mp4)

- `527` frames, IDs `0–526`, primer y último frame legibles;
- orientación `2746×1536`;
- VFR preservado con múltiples intervalos;
- `ev_010` visible exactamente en frame 463 con timestamp `9.221667`;
- SHA-256: `d68df49ccd895722eaf976a1d36714d7c72042bb4dd25ba58384b81571fdcb31`.

### Timeline y contact sheet

[events_timeline.png](/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/nivel_a2_01/stage_4/events_timeline.png)
contiene 10 eventos visibles, incluido el quinto bote y `ev_010` después de `ev_009`.

[events_contact_sheet.png](/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/nivel_a2_01/stage_4/events_contact_sheet.png)
contiene 10 secciones en orden, con `[461, 462, 463, 464, 465]` para `ev_010`.

### Revisión focalizada del último bote

[final_bounce_review.mp4](/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/nivel_a2_01/stage_4/final_bounce_review.mp4)
es una revisión canónica VFR de 53 frames (`428–480`) que incluye `ev_009`, `ev_010`,
tracking opcional y las etiquetas `ULTIMO GOLPE | ev_009` y `BOTE TERMINAL | ev_010`.

[final_bounce_contact_sheet.png](/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/nivel_a2_01/stage_4/final_bounce_contact_sheet.png)
contiene exactamente los frames `459–467` y marca `463` con borde y etiqueta visible.

## Validación automática

- `uv run pytest`: 160 passed;
- `uv run ruff check .`: passed;
- `uv run python -m compileall src scripts tests`: passed;
- `uv run python scripts/replit_smoke_test.py`: passed;
- `git diff --check`: passed.

Los tests cubren diez eventos, conservación de `ev_001`–`ev_009`, `ev_010` en frame 463,
cinco botes, loader VFR, overlay de 527 frames, timeline, contact sheet, revisión
terminal y compatibilidad histórica CFR.

## Gate humano final y límites

El usuario confirmó que `ev_001`–`ev_010` representan todos los saques, golpes y botes
visibles; `ev_010` es el último bote real en frame 463 (`9.221667 s`, `side=far`).
Veredicto humano: **A**. Stage 4 A2 queda `CLOSED_SUCCESSFULLY`.

RunPod, SSH, GPU y WASB no se utilizaron; Stage 2 y Stage 3 no se recalcularon; el
anotador no se reabrió.
