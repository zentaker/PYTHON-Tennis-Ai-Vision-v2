# Stage 5B v2 — Ejecución anclada A2

**Estado técnico:** `ANCHORED_BALLISTIC_MARGINAL`

Se ejecutaron 24 solves reales, cada uno con 16 starts deterministas y cinco alturas.
La combinación seleccionada fue `ev_008=400` (resto: 139,158,200,262,287,327,351,434,463),
coste real `28877.6947`, segunda `29572.8270`, margen `695.1323`.

Eventos seleccionados, en metros:

| Evento | X | Y | Z | Restricción |
|---|---:|---:|---:|---|
| ev_001 | 1.075 | -2.467 | 1.030 | PASS |
| ev_002 | -0.949 | 4.418 | 0.000 | PASS |
| ev_003 | -2.563 | 11.8851 | 2.507 | PASS, detrás de far |
| ev_004 | 1.189 | -7.250 | 0.000 | PASS |
| ev_005 | 1.261 | -18.996 | 3.917 | PASS |
| ev_006 | -3.743 | 10.402 | 0.000 | PASS |
| ev_007 | -4.201 | 3.504 | 3.594 | PASS |
| ev_008 | 2.965 | -3.012 | 0.000 | PASS |
| ev_009 | 5.328 | -10.628 | 1.918 | PASS |
| ev_010 | 3.691 | 10.125 | 0.000 | PASS |

La continuidad máxima y los cinco errores de bote son `0.0 m` por construcción. La
velocidad máxima es `37.289 m/s`; el máximo de reproyección observado es `68.992 px` y
varios segmentos son marginales. Por eso el resultado no se fuerza a READY aunque
`ev_003` sí cumple `Y > +11.885 m`.

La incertidumbre usa los costes y parámetros de las 24 soluciones reales, más
perturbaciones reproducibles de píxel/cámara; los percentiles están en
`uncertainty_report.json`. No se ejecutaron RunPod, SSH, GPU, WASB, Stage 2/3/4, Stage
5C ni Stage 6.
