# Stage 5A.1 — Evaluación de referencia vertical A2

**Estado calculado:** `READY_FOR_STAGE_5B`  
**Referencia humana SHA-256:** `e33512a98b0e1acad00ae7eef2c4e5fc820a0538c8f7b06e8e6ea0ca04644b73`  
**Candidato seleccionado:** `f1.90_dx0_dy0`

La referencia humana existente se preservó byte a byte y se respaldó antes de evaluar.
Contiene exactamente `net_center_base`, `net_center_top`, `net_post_base` y
`net_post_top`; no se repitieron clics.

## Modelo y errores

El modelo refinado usa float64 y las ocho correspondencias de suelo más las cuatro
referencias no coplanares. Sus intrínsecos son aproximadamente `fx=4816.90`,
`fy=4473.61`, `cx=1407.82`, `cy=2074.31`; centro de cámara
`[-0.046, -39.859, 10.512] m` y altura estimada `10.512 m`. Son parámetros inferidos,
no ground truth.

- Error suelo: media `4.416 px`, máximo `8.913 px`.
- Error vertical: media `3.946 px`, máximo `7.633 px`.
- Bias vertical medio: `-1.085 px`.
- Sensibilidad anterior: `117.5 px`.
- Sensibilidad nueva (jitter ±2 px, máximo 3/5 m): `35.713 px`.
- Mejora calculada: `69.61%`.

La evaluación real considera 35 candidatos, errores separados de suelo/verticales,
profundidad positiva, cámara sobre el suelo, rotación válida, degradación del plano,
familia de modelos y estabilidad ante jitter.

## Jitter reproducible

Se ejecutaron 200 soluciones válidas por cada nivel con semilla `20260716`:

| perturbación | altura p05–p50–p95 (m) | proyección p95 a 3 m | proyección p95 a 5 m |
| --- | --- | ---: | ---: |
| ±1 px | 10.398–10.505–10.636 | 2.77 px | 5.53 px |
| ±2 px | 10.256–10.494–10.808 | 5.85 px | 12.72 px |
| ±3 px | 10.115–10.502–10.932 | 7.82 px | 15.47 px |

Los umbrales definidos antes de ejecutar fueron: vertical media ≤5 px, máxima ≤10 px,
suelo media ≤8 px, máxima ≤18 px, p95 a 3 m ≤15 px, p95 a 5 m ≤25 px, variación de
altura ≤15%, profundidad positiva y ausencia de bias sistemático. Todos pasaron.

## Artefactos

- `outputs/nivel_a2_01/stage_5a1/camera_model_refined.json`
- `outputs/nivel_a2_01/stage_5a1/vertical_calibration_report.json`
- `outputs/nivel_a2_01/stage_5a1/vertical_candidate_comparison.csv`
- `outputs/nivel_a2_01/stage_5a1/vertical_jitter_report.json`
- `outputs/nivel_a2_01/stage_5a1/readiness_report.json`
- `outputs/nivel_a2_01/stage_5a1/vertical_calibration_overlay.png`
- `outputs/nivel_a2_01/stage_5a1/vertical_calibration_closeup.png`

La ejecución no recalculó Stage 2/3, no modificó Stage 4 y no inició Stage 5B. La
decisión `READY_FOR_STAGE_5B` queda registrada, pero Stage 5B no se ejecuta en esta
pasada; requiere una instrucción posterior.
