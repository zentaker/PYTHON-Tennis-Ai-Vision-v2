# Exit report — Stage 2 A2

**Estado final:** `CLOSED_SUCCESSFULLY`
**Fecha de cierre:** 2026-07-15
**Veredicto humano:** `A — APROBADA`

## Ejecución técnica aprobada

- Inferencia ejecutada sobre NVIDIA RTX A5000 mediante CUDA.
- Commit de ejecución:
  `421fe01a3721ffcdc38f89a37316a9277797e5f3`.
- Video fuente verificado por SHA-256:
  `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- `527/527` frames procesados y `527` filas consecutivas en el CSV.
- Timeline VFR preservada y timestamps estrictamente monótonos.
- Resolución y orientación canónica: `2746x1536`.
- Puntos detectados dentro de los bounds canónicos.
- Overlay de `527` frames con primer y último frame legibles.

## Validación visual aprobada

El usuario revisó el comparativo completo de Stage 2 raw y Stage 3 debug. Confirmó que
la pelota está correctamente trackeada, que la detección raw es visualmente suficiente
y que Stage 2 alcanzó su objetivo.

> El usuario revisó el video comparativo y confirmó que el tracking de la pelota es
> correcto y que Stage 2 obtuvo su objetivo.

Los errores y gaps técnicos documentados en el gate visual no impiden el objetivo de
este clip. El veredicto humano final es `A`.

## Cierre

La ejecución técnica y el gate visual están aprobados. Stage 2 queda cerrada
exitosamente y no necesita repetirse para `nivel_a2_01`.

Evidencia completa:
`docs/levels/level_a2/stage_2_stage_3_visual_gate.md`.
