# Reporte Stage 1 — Nivel A2

**Fecha:** 2026-07-14

**Estado:** cerrada exitosa; gates numérico y visual aprobados

## Entrada aprobada

- `clip_id`: `nivel_a2_01`.
- MP4 fuente: `data/clips/nivel_a2_01/source.mp4`.
- SHA-256 del MP4: `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- Frame seleccionado: `180`, opción 01.
- Frame canónico: `data/clips/nivel_a2_01/reference_frame.png`.
- Resolución canónica: `2746x1536` horizontal.
- Layout: `doubles`.
- Método de captura: `manual_web_click`, sin calibration guide.
- Método de homografía: `cv2.findHomography(method=0)`, sin RANSAC.

## Ocho puntos capturados

| Punto | x (px) | y (px) |
| --- | ---: | ---: |
| `far_left` | 835 | 403 |
| `far_right` | 1907 | 407 |
| `near_left` | 469 | 1176 |
| `near_right` | 2278 | 1180 |
| `far_left_service` | 933 | 523 |
| `far_right_service` | 1811 | 524 |
| `near_left_service` | 796 | 916 |
| `near_right_service` | 1947 | 916 |

Los puntos fueron enviados por la UI web y persistidos en
`data/clips/nivel_a2_01/court_corners_pixel.json`. El JSON conserva la ruta del frame A2,
layout `doubles`, método `manual_web_click`, orden explícito y no contiene `guide_path`.

## Homografía y métricas

La homografía píxel → cancha y su inversa quedaron en
`data/clips/nivel_a2_01/homography.json`, junto con las correspondencias, dimensiones,
`clip_id`, fecha y métricas por punto.

| Métrica | Resultado | Umbral |
| --- | ---: | ---: |
| Error medio court → pixel | `4.705469 px` | `< 5 px` |
| Error máximo court → pixel | `8.598912 px` | `< 15 px` |
| Error medio pixel → court | `0.053271 m` | Informativo |
| Error máximo pixel → court | `0.090394 m` | Informativo |

El gate numérico pasó en el primer intento, sin relajar umbrales ni cambiar a RANSAC.

## Evidencia generada

- Puntos y labels: `outputs/nivel_a2_01/stage_1/calibration_clicks_preview.png`.
- Cancha reproyectada: `outputs/nivel_a2_01/stage_1/reference_frame_with_reprojected_court.png`.
- Vista 2D: `outputs/nivel_a2_01/stage_1/court_2d_top.png`.
- Métricas: `outputs/nivel_a2_01/stage_1/reprojection_error_report.json`.

## Orientación y riesgos

La metadata de rotación `270°` del MP4 sigue siendo el riesgo principal. La calibración no
usa el frame lateral `1536x2746`; usa el frame horizontal `2746x1536`. La verificación
completa y el contrato para futuros detectores están en
`docs/levels/level_a2/stage_1_orientation_validation.md`.

Stage 2 deberá normalizar el video antes de usar la homografía. No se ejecutó WASB, no se
instaló tracker/PyTorch y no se crearon detecciones de pelota.

## Gate

- Gate numérico: **aprobado**.
- Inspección técnica de orientación: **aprobada**.
- Gate visual humano: **aprobado por el usuario** el 2026-07-14.
- Archivo de revisión humana:
  `outputs/nivel_a2_01/stage_1/reference_frame_with_reprojected_court.png`.

El usuario confirmó que la reproyección coincide visualmente con las líneas reales de la
cancha. Stage 1 A2 queda cerrada exitosamente y se autoriza preparar Stage 2 para ejecución
externa; este cierre no autoriza ejecutar WASB en macOS.
