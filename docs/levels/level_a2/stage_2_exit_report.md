# Exit report provisional — Stage 2 A2

**Estado:** `TECHNICALLY_EXECUTED_PENDING_HUMAN_VISUAL_GATE`
**Fecha:** 2026-07-15

## Evidencia técnica satisfecha

- Inferencia CUDA sobre NVIDIA RTX A5000.
- Commit de ejecución:
  `421fe01a3721ffcdc38f89a37316a9277797e5f3`.
- Video fuente verificado por SHA-256:
  `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- `527/527` frames procesados y `527` filas consecutivas en el CSV.
- Timestamps VFR estrictamente monótonos.
- Puntos detectados dentro de `2746x1536`.
- Overlay de `527` frames, orientación canónica y último frame legible.
- Reporte y logs descargados y reconciliados.

## Gate no satisfecho

No existe aún un veredicto humano sobre el overlay completo. Por ello Stage 2 no está
visualmente aprobada ni cerrada, aunque su ejecución técnica terminó con éxito.

## Próxima acción humana

Revisar:

`outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`

y registrar un veredicto explícito. Este exit report no autoriza el inicio de Stage 4
ni Stage 5.
