# Reporte baseline — Stage 3 A2

**Fecha:** 2026-07-15
**Estado:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`

## Resultado

La primera y única baseline local procesó las `527` detecciones de Stage 2 con timestamps
VFR. No se ejecutó WASB, no se usó GPU y no se modificó el video fuente.

## Métricas

- Frames totales: `527`.
- Detecciones raw: `383`.
- `detected`: `383`.
- `rejected`: `0`; frames rechazados: ninguno; razones: ninguna.
- `interpolated`: `19`.
- `missing`: `125`.
- Cobertura final: `402/527` (`76.2808%`).
- Gaps interpolados: `8`.
- Gap interpolado máximo: `6` frames, `0.116666 s`.
- Gap ausente máximo: `81` frames, `1.588333 s`.
- Velocidad raw máxima: `4550.819943 px/s`.
- Velocidad smooth máxima: `4689.589387 px/s`.
- Warning: permanecen frames ausentes porque algunos gaps exceden los límites o no
  tienen ambos extremos.

Que la baseline no rechace frames no es una conclusión visual. El límite efectivo de
`4719.595004 px/s` quedó por encima del máximo raw observado y no se reajustó después del
run. La revisión humana debe determinar si algún spike requiere una segunda pasada.

## Gaps interpolados

| Frames | Cantidad | Duración real |
| --- | ---: | ---: |
| 189 | 1 | 0.033334 s |
| 191–196 | 6 | 0.116666 s |
| 199–200 | 2 | 0.050000 s |
| 203–204 | 2 | 0.066667 s |
| 262–264 | 3 | 0.083333 s |
| 364 | 1 | 0.033333 s |
| 485 | 1 | 0.033334 s |
| 506–508 | 3 | 0.083333 s |

## Artefactos y validación técnica

- `outputs/nivel_a2_01/stage_3/smoothed_trajectory.csv`: `527` filas, IDs `0–526`,
  timestamps idénticos al sidecar y puntos smooth dentro de bounds.
- `outputs/nivel_a2_01/stage_3/smoothed_trajectory_overlay.mp4`: `527` frames,
  `2746x1536`, `10.471668 s`, primer y último frame legibles.
- `outputs/nivel_a2_01/stage_3/trajectory_debug_overlay.mp4`: `527` frames,
  `2746x1536`, `10.471668 s`, primer y último frame legibles.
- `outputs/nivel_a2_01/stage_3/trajectory_quality_report.json`: parámetros, métricas,
  gaps y metadata de outputs.
- `outputs/nivel_a2_01/stage_3/stage_3_review_contact_sheet.png`: `1920x1432`, 12
  muestras de interpolación, saltos raw/smooth, gaps largos y confidence baja.

Los overlays preservan la timeline VFR y orientación canónica; la duración reportada
termina en el timestamp del último frame (`10.471668 s`), coherente con el sidecar.

## Limitaciones y gate

- La hoja de contacto no sustituye la revisión de ambos videos completos.
- No se valida aún que la trayectoria smooth coincida visualmente con la pelota.
- No se implementó física 3D ni detección de eventos.
- Stage 4 y Stage 5 no fueron iniciadas.

Stage 3 permanece pendiente de veredicto humano explícito.
