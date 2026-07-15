# Stage 4 A2 — Reporte de ejecución

**Estado:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`

**Fecha:** 2026-07-15

**Commit base:** `a0c3498b1f387ff3d44169350e7dfea2573901a0`

## Persistencia y recuperación

La fuente canónica fue el archivo final escrito por el anotador:
`data/clips/nivel_a2_01/manual_annotation.json`.

| Evidencia | Estado | Tamaño | Eventos | SHA-256 |
| --- | --- | ---: | ---: | --- |
| Archivo final | JSON válido | 4081 B | 9 | `1e540abe1ef3545969d84d07763c132adcf851788e6fe51a14999a4a3cda0e84` |
| Borrador | JSON válido | 4081 B | 9 | `1e540abe1ef3545969d84d07763c132adcf851788e6fe51a14999a4a3cda0e84` |
| `GET /api/events` | Respuesta válida | — | 9 | — |
| `GET /api/session` | `PASSED_30_30`, ready | — | — | — |

Final y borrador eran byte a byte idénticos. El endpoint confirmó los mismos nueve
eventos, por lo que no se aplicó recuperación ni reconstrucción desde la captura.

Antes de normalizar se crearon y verificaron estos backups ignorados por Git:

- `outputs/nivel_a2_01/stage_4/backups/manual_annotation_before_normalization_20260715T123801-0500.json`;
- `outputs/nivel_a2_01/stage_4/backups/annotation_draft_20260715T123801-0500.json`.

Ambos conservan el SHA-256 `1e540abe1ef3545969d84d07763c132adcf851788e6fe51a14999a4a3cda0e84`.

## Auditoría contra el respaldo humano

Los nueve eventos coinciden exactamente en cantidad, orden, tipo, jugador, lado,
frames y timestamps con la captura autoritativa proporcionada por el usuario. Cada
timestamp también coincide con `frame_timestamps.json` con error menor a un microsegundo.

| ID | Tipo | Jugador | Lado | Frames | Cantidad | Timestamps (s) | Resultado |
| --- | --- | --- | --- | --- | ---: | --- | --- |
| ev_001 | serve | near | near | 139–139 | 1 | 2.771667–2.771667 | PASS |
| ev_002 | bounce | unknown | far | 158–158 | 1 | 3.138333–3.138333 | PASS |
| ev_003 | hit | far | far | 200–200 | 1 | 3.955000–3.955000 | PASS |
| ev_004 | bounce | unknown | near | 262–264 | 3 | 5.188333–5.238333 | PASS |
| ev_005 | hit | near | near | 287–288 | 2 | 5.688333–5.721667 | PASS |
| ev_006 | bounce | unknown | far | 327–327 | 1 | 6.488333–6.488333 | PASS |
| ev_007 | hit | far | far | 351–351 | 1 | 6.971667–6.971667 | PASS |
| ev_008 | bounce | unknown | near | 399–400 | 2 | 7.938333–7.955000 | PASS |
| ev_009 | hit | near | near | 434–435 | 2 | 8.638333–8.655000 | PASS |

Conteos: `serve=1`, `bounce=4`, `hit=4`; jugador `near=3`, `far=2`, `unknown=4`;
lado `near=5`, `far=4`; eventos puntuales `5`; eventos multiframe `4`.

## Normalización

El loader acepta ahora `--annotation`, `--output`, `--frame-timestamps` y `--clip-id`.
Para A2 exige timestamps explícitos derivados del índice VFR, conserva rangos inclusivos
y registra `clip_id=nivel_a2_01`, `timing_mode=variable_frame_rate` y
`frames_total=527`. El modo histórico basado en FPS se conserva para Madrid.

Resultado:

- `outputs/nivel_a2_01/stage_4/events.json`;
- 9 eventos, mismos IDs, orden, categorías, rangos, timestamps, notas y fuente;
- SHA-256: `0a63fc219adad385684f92c2ae12e54574f53e7e367a9270631e09ae51c500f0`.

## Material de revisión

### Overlay

`outputs/nivel_a2_01/stage_4/events_overlay.mp4`

- modo `canonical_vfr`;
- H.264, `2746×1536`;
- 527 frames decodificados, IDs `0–526`;
- duración reportada `10.471668 s`, coherente con el timestamp del último frame;
- intervalos observados `0.016666`, `0.016667`, `0.021667` y `0.033334 s`;
- primer y último frame legibles;
- eventos puntuales y fases `START`, `ACTIVE`, `END` verificadas;
- SHA-256: `157464605646fd9bb74ccac1f42c9fdca889e7057c215d83d2527897277936b9`.

### Timeline

`outputs/nivel_a2_01/stage_4/events_timeline.png`

- eje temporal VFR;
- 9 eventos visibles, incluidos los cinco eventos puntuales;
- tabla inferior con rangos y tiempos completos;
- imagen legible de `2316×1259`;
- SHA-256: `1452398914eae60f1d49effbf9c3ec2e6f9465a802c01feff92e7a035bce9ed6`.

### Contact sheet

`outputs/nivel_a2_01/stage_4/events_contact_sheet.png`

- 9 secciones en orden `ev_001`–`ev_009`;
- cinco vistas contextuales por evento;
- frames puntuales sin imágenes duplicadas;
- IDs, timestamps, tipo y jugador/lado visibles;
- imagen legible de `1800×2646`;
- SHA-256: `aed2177e8109077f81a9d70502bcaa7301bd7aa14ec374cba37cc662c178c7ac`.

El reporte de máquina está en
`outputs/nivel_a2_01/stage_4/events_report.json`.

## Validación automática

- `uv run pytest`: 157 passed;
- `uv run ruff check .`: passed;
- `uv run python -m compileall src scripts tests`: passed;
- `uv run python scripts/replit_smoke_test.py`: passed;
- `git diff --check`: passed.

Los tests cubren la anotación A2 de nueve eventos, frame→timestamp, eventos puntuales y
multiframe, orden, IDs duplicados, bounds, loader VFR, overlay canónico de 527 frames,
VFR, último frame, timeline, contact sheet y compatibilidad histórica CFR.

## Límites y gate

Los eventos siguen siendo evidencia humana, no detecciones automáticas. La inspección
técnica confirmó que los artefactos son legibles y estructuralmente correctos, pero no
reemplaza el juicio visual del usuario.

Stage 4 permanece abierta en `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`. Stage 2 y Stage 3
no se recalcularon; RunPod, SSH, GPU y WASB no se utilizaron; Stage 5 no comenzó.
