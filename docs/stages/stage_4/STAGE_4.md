# STAGE 4 - Deteccion de eventos

**Estado:** Preparada, no iniciada  
**Nivel:** A  
**Fecha de preparacion:** 2026-05-19

## Proposito

Convertir la narracion/manual annotation del rally en eventos internos de botes y golpes para alimentar las etapas de visualizacion posteriores.

En Nivel A, Stage 4 no implementa deteccion automatica de eventos. Lee `narrative_events` desde una anotacion manual para aislar la visualizacion del problema de deteccion automatica.

## Regla de Nivel A

Stage 4 Nivel A debe leer `narrative_events` desde:

```text
data/reference_clip/manual_annotation.json
```

Si `manual_annotation.json` no existe, Stage 4 debe iniciar creando/completando ese archivo a partir de conocimiento de dominio y validacion humana.

No se debe avanzar a Stage 5 hasta validar que los eventos fueron leidos sin perdida ni alteracion.

## Inputs esperados

- `outputs/stage_3/smoothed_trajectory.csv`
- `data/reference_clip/manual_annotation.json`
- `data/reference_clip/homography.json`

Inputs auxiliares:

- `data/reference_clip/madrid_R1.mov`
- `outputs/stage_3/smoothed_trajectory_overlay.mp4`
- `docs/stages/stage_3/exit_report.md`

## Outputs esperados

- `outputs/stage_4/events.json`
- `docs/stages/stage_4/events_report.md`

Los outputs en `outputs/stage_4/` seran locales e ignorados por Git. La documentacion y scripts asociados si deben versionarse.

## Definition of Done preliminar

- Existe `data/reference_clip/manual_annotation.json` completo para Nivel A.
- El parser lee `narrative_events`.
- Se genera `outputs/stage_4/events.json`.
- No hay perdida ni alteracion de eventos respecto al JSON manual.
- Existe reporte `docs/stages/stage_4/events_report.md`.
- El usuario valida que los eventos corresponden al rally.

## Gate

Validacion humana de eventos.

El usuario debe confirmar que:

- los botes esperados estan presentes;
- los golpes esperados estan presentes;
- los frame ranges son razonables;
- no se inventaron eventos;
- no faltan eventos narrados.

## Fuera de alcance en Nivel A

- Deteccion automatica de botes.
- Deteccion automatica de golpes.
- Estimacion de altura.
- Render final de vista superior.
- Render final de vista lateral.

## Estado actual

Stage 4 queda preparada documentalmente. No se implemento codigo ni se detectaron eventos en esta sesion.
