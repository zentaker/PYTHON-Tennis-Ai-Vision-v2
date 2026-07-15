# Events Report — Stage 4 Nivel A

**Estado A2:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`

**Fecha:** 2026-07-15

La anotación humana real de `nivel_a2_01` quedó persistida con 9 eventos y fue
normalizada sin alterar IDs, orden, categorías, rangos, timestamps, notas o fuente.
Final, borrador y endpoint fueron concordantes; se crearon backups antes de ejecutar el
pipeline.

El soporte A2 valida cada timestamp contra el índice VFR, renderiza los 527 frames en
orientación canónica `2746×1536` y conserva el último frame. El camino CFR histórico de
Madrid permanece disponible.

Artefactos locales:

- `outputs/nivel_a2_01/stage_4/events.json`;
- `outputs/nivel_a2_01/stage_4/events_overlay.mp4`;
- `outputs/nivel_a2_01/stage_4/events_timeline.png`;
- `outputs/nivel_a2_01/stage_4/events_contact_sheet.png`;
- `outputs/nivel_a2_01/stage_4/events_report.json`.

Conteos: un saque, cuatro botes y cuatro golpes; cinco eventos puntuales y cuatro
multiframe. La suite completa pasó con 157 tests.

La evidencia, hashes, tabla de los nueve eventos y validaciones se encuentran en
`docs/levels/level_a2/stage_4_execution_report.md`.

Stage 4 no está cerrada: falta el gate visual humano. Stage 5 no ha comenzado.
