# Stage 5A A2 — Cámara y observabilidad

**Estado:** `CLOSED_WITH_REFINED_VERTICAL_CALIBRATION`
**Decisión de readiness:** `READY_FOR_STAGE_5B`
**Método:** `ASSUMPTION_BASED_MONOCULAR_CALIBRATION`

## Convención 3D

Se conserva la convención histórica de la homografía y se hace explícita como sistema
diestro en metros: origen en el centro geométrico de la cancha (punto medio de la red),
X positivo de izquierda a derecha, Y positivo desde la red hacia la línea de fondo lejana,
Y=0 en el plano de la red, Z=0 en el plano de la cancha y Z positivo hacia arriba.
Así, X×Y=Z. No se presenta ninguna altura como ground truth.

## Auditoría de homografía

La entrada `data/clips/nivel_a2_01/homography.json` no fue reemplazada. Sus ocho
correspondencias doubles y dimensiones reglamentarias son las de Stage 1; la inversa
compone con error máximo `5.64e-15`. El error existente court→pixel es media
`4.705469 px`, máximo `8.598912 px`; pixel→court es media `0.053271 m`, máximo
`0.090394 m`. La orientación canónica `2746×1536`, far-above-near y left-before-right
pasó la validación.

## Candidatos

Se generaron 35 candidatos (focales 1.60–2.40 veces el ancho y offsets de principal point
±100/±75 px). Todos los candidatos físicos que conservan profundidad positiva se guardan
en `outputs/nivel_a2_01/stage_5a/camera_candidates.json` y `.csv`; no se descartaron los
alternativos casi equivalentes. Se seleccionó para el overlay `f2.00_dx100_dy0`, por el
menor error entre esta búsqueda controlada, no como calibración exacta.

Intrínsecos seleccionados: `fx=fy=5492`, `cx=1473`, `cy=768`, `skew=0`. El modelo
reproduce las ocho referencias con media `5.294 px` y máximo `14.237 px`, y 100% de
profundidades positivas. Centro estimado `[0.084, -43.621, 11.215] m`; altura estimada
`11.215 m`; yaw `0.075°`, pitch `-0.940°`, roll `105.200°` (ángulos ZYX diagnósticos).
Son supuestos monoculares, no mediciones de campo.

## Sensibilidad vertical

Al proyectar alturas virtuales `0.5, 0.914, 1.07, 2, 3 y 5 m`, candidatos igualmente
válidos divergen hasta `117.5 px` en el punto de la red. La homografía solo constriñe
Z=0: aplicar H a una pelota elevada devuelve la intersección aparente con el suelo, no
su posición real. Por eso la decisión es `NEEDS_VERTICAL_REFERENCE` y no se inicia 5B.

La intervención mínima propuesta es anotar dos puntos de un poste de red (base y parte
superior), o una estructura vertical equivalente de altura conocida. No se solicita al
usuario inventar una altura.

## Vuelos y observabilidad

Los diez eventos producen nueve segmentos consecutivos. Los nueve tienen suficientes
observaciones 2D para un ajuste futuro; `flight_07` tiene cobertura `39/50 = 0.78` y
conserva sus 11 frames faltantes como advertencia. Los cinco eventos `bounce` imponen
Z=0; serve/hit dejan Z desconocida. El último segmento es `ev_009 → ev_010` y termina en
frame 463. No se ajustaron parábolas ni se reconstruyó una trayectoria 3D.

## Artefactos

- `outputs/nivel_a2_01/stage_5a/homography_audit.json`
- `outputs/nivel_a2_01/stage_5a/camera_candidates.json`
- `outputs/nivel_a2_01/stage_5a/camera_candidates.csv`
- `outputs/nivel_a2_01/stage_5a/camera_model.json`
- `outputs/nivel_a2_01/stage_5a/camera_reprojection_overlay.png` y `.mp4`
- `outputs/nivel_a2_01/stage_5a/vertical_reference_overlay.png`
- `outputs/nivel_a2_01/stage_5a/vertical_sensitivity_report.json`
- `outputs/nivel_a2_01/stage_5a/flight_segments.json`
- `outputs/nivel_a2_01/stage_5a/readiness_report.json`

RunPod, SSH, GPU, WASB, Stage 2 y Stage 3 no se utilizaron en esta pasada.
