# Exit report — Stage 1 Nivel A2

**Clip:** `nivel_a2_01`

**Fecha de cierre:** 2026-07-14

**Resultado:** cerrada exitosa

## Inputs

- Fuente: `data/clips/nivel_a2_01/source.mp4`.
- SHA-256: `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- Frame aprobado: frame 180, opción 01.
- Frame canónico: `data/clips/nivel_a2_01/reference_frame.png`, `2746x1536`.
- Layout: `doubles`.
- Captura: `manual_web_click`.
- Homografía: `cv2.findHomography(method=0)`.

## Correspondencias humanas

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

## Métricas y outputs

- Error medio court → pixel: `4.705469 px` (`< 5 px`).
- Error máximo court → pixel: `8.598912 px` (`< 15 px`).
- Error medio pixel → court: `0.053271 m`.
- Error máximo pixel → court: `0.090394 m`.
- Corners: `data/clips/nivel_a2_01/court_corners_pixel.json`.
- Homografía: `data/clips/nivel_a2_01/homography.json`.
- Preview: `outputs/nivel_a2_01/stage_1/calibration_clicks_preview.png`.
- Overlay: `outputs/nivel_a2_01/stage_1/reference_frame_with_reprojected_court.png`.
- Vista superior: `outputs/nivel_a2_01/stage_1/court_2d_top.png`.
- Reporte numérico: `outputs/nivel_a2_01/stage_1/reprojection_error_report.json`.

## Gates

- Gate numérico: aprobado en el primer intento.
- Gate técnico de orientación: aprobado.
- Gate visual: aprobado por el usuario tras revisar el overlay y confirmar que la
  reproyección coincide con las líneas reales.

## Contrato que pasa a Stage 2

El MP4 declara rotación `270°` y OpenCV puede decodificar `1536x2746`. La homografía solo
acepta coordenadas en el espacio horizontal `2746x1536`. El contrato obligatorio es:

`raw video frame -> canonical orientation 2746x1536 -> detector coordinates -> homography`

## Decisión de salida

Stage 1 A2 se cierra exitosamente. Stage 2 queda autorizada únicamente para preparación y
ejecución posterior en Linux/WSL/GPU compatible. No se autoriza inferencia WASB en este
Mac, ni el inicio de Stage 3, Stage 4 real o Stage 5.
