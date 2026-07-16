# Events Report — Stage 4 Nivel A

**Estado A2:** `CLOSED_SUCCESSFULLY`

**Fecha:** 2026-07-15

La primera anotación tenía 9 eventos. El usuario añadió el décimo bote terminal
`ev_010` en frame 463 y volvió a guardar. Final, borrador y endpoint quedaron
concordantes con 10 eventos; los nueve anteriores no cambiaron y se crearon nuevos
backups antes de ejecutar el pipeline.

El soporte A2 valida cada timestamp contra el índice VFR, renderiza los 527 frames en
orientación canónica `2746×1536` y conserva el último frame. El camino CFR histórico de
Madrid permanece disponible.

Artefactos locales:

- `outputs/nivel_a2_01/stage_4/events.json`;
- `outputs/nivel_a2_01/stage_4/events_overlay.mp4`;
- `outputs/nivel_a2_01/stage_4/events_timeline.png`;
- `outputs/nivel_a2_01/stage_4/events_contact_sheet.png`;
- `outputs/nivel_a2_01/stage_4/events_report.json`.

Conteos: un saque, cinco botes y cuatro golpes; seis eventos puntuales y cuatro
multiframe. La suite completa pasó con 160 tests.

La evidencia, hashes, tabla de los nueve eventos y validaciones se encuentran en
`docs/levels/level_a2/stage_4_execution_report.md`.

Gate humano final: **A — CLOSED_SUCCESSFULLY**. El usuario confirmó que el bote terminal
`ev_010` (frame 463, `9.221667 s`, `side=far`) es correcto y que no faltan eventos.
Stage 5A queda en progreso; Stage 5B no se ha iniciado.
