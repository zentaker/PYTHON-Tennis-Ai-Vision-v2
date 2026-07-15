# Exit report — Stage 3 A2

**Estado final:** `CLOSED_SUCCESSFULLY`
**Fecha de cierre:** 2026-07-15
**Veredicto humano:** `A — APROBADA`

## Resultado técnico conservado

- Frames totales: `527`.
- Frames con trayectoria final: `402`.
- Cobertura final: `402/527` (`76.2808%`).
- `detected`: `383`.
- `interpolated`: `19`.
- `missing`: `125`.
- `rejected`: `0`.
- Gaps interpolados: `8`.
- Gap missing máximo: `81` frames / `1.588333 s`.
- Overlays: `527` frames, `2746x1536`, orientación canónica y timeline VFR
  preservadas.

Estas cifras no significan que todos los frames contengan una pelota detectada o una
trayectoria final. Los gaps, la cobertura parcial y la ausencia de rechazos permanecen
documentados como propiedades reales de la baseline.

## Gate visual aprobado

El usuario revisó el comparativo completo y confirmó que la pelota está correctamente
trackeada, que la trayectoria suavizada es visualmente correcta y que el resultado es
aceptable para continuar. Los gaps conocidos no invalidan el objetivo alcanzado para
este clip.

El veredicto humano final de Stage 3 es `A`.

## Cierre

Stage 3 queda cerrada exitosamente. No se recalculó la baseline ni se modificaron sus
parámetros para registrar este cierre. La siguiente actividad autorizada es la anotación
manual de eventos de Stage 4; Stage 5 no está iniciada.

Evidencia:

- `docs/levels/level_a2/stage_3_baseline_report.md`;
- `docs/levels/level_a2/stage_2_stage_3_visual_gate.md`.
