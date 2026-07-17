# Stage 5B v1 — Rechazo del gate humano

**Estado:** `REJECTED_BY_HUMAN_GATE`

El baseline v1, ejecutado desde el commit `095fd9078e4b41849d5b9fb2083f7c16d6979bee`, fue
rechazado visualmente. En `ev_003` el jugador lejano golpea detrás de la baseline far,
pero la vista superior no representó esa ubicación y la vista lateral no permitió
comprobarla. Otros frames presentaron ambigüedad geométrica similar.

La causa está acotada a Stage 5B v1: su fitter tenía continuidad posterior a la
optimización, un único solve real para las 24 combinaciones, continuidad no incluida en
el residual, `max_nfev=8`, y una incertidumbre proxy basada en cobertura. Sus renderers
usaban escalas no isotrópicas y no mostraban correctamente baselines, exteriores y
orientación métrica.

Resultado v1: 3 `FIT_ACCEPTED`, 6 `FIT_MARGINAL`, p95 global `50.258 px`, continuidad
máxima `1.511 m` y error de bote máximo `0.354 m`.

Los cuatro artefactos v1 se preservan sin sobrescritura en
`outputs/nivel_a2_01/stage_5b/` y no se eliminan:

- `trajectory_3d.csv`: `22b4cbb0e75215d0798cdfeeacfd5508e7723e1a4132b13152771eded8798dc9`
- `segment_fits.json`: `ede128ea8cbcd2967696e4a308dff91bc6ba36255c24525fa40c2f08e3493b16`
- `event_frame_selection.json`: `49c0b01e874beb350ad1958109c3d6258caa97e152c8bcef9e1a9a739098d3d7`
- `stage_5b_human_gate.mp4`: `84bdbec8ac3708841d63086d3196d1d33af2eda6365d2e1459903a7f2f765404`

Stage 2, Stage 3, Stage 4, homografía, referencia vertical y cámara refinada no son
parte del rechazo.
