# STAGE 2 - Deteccion de pelota

**Estado:** Cerrada exitosa con limitaciones conocidas  
**Nivel:** A  
**Fecha de cierre:** 2026-05-19

## Proposito

Validar si WASB-SBDT con pesos preentrenados de tenis puede detectar la pelota en el clip de referencia Nivel A y producir coordenadas por frame suficientes para continuar el pipeline.

El objetivo de esta etapa no fue generar una trayectoria final suavizada ni medir eventos fisicos. El objetivo fue un veredicto de viabilidad visual sobre detecciones de pelota.

## Entregables completados

- WASB-SBDT disponible localmente en `third_party/WASB-SBDT`.
- Checkpoint local `models/wasb/wasb_tennis_best.pth.tar`.
- Runner minimo versionado en `src/tracker/wasb_runner.py`.
- CSV local de detecciones: `data/reference_clip/wasb_detections.csv`.
- Overlay MP4 local: `outputs/stage_2/wasb_detections_overlay.mp4`.
- Auditoria de continuidad local: `docs/stages/stage_2/local_continuity_audit.md`.
- Reporte de cierre: `docs/stages/stage_2/exit_report.md`.

## Gate visual

El usuario reviso:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_2\wasb_detections_overlay.mp4
```

Veredicto humano:

```text
A) WASB es visualmente aceptable y suficientemente viable para continuar.
```

## Resultado

Stage 2 pasa el gate visual de Nivel A como viable con limitaciones conocidas.

Metricas tecnicas del run:

- Frames totales/procesados: `949 / 949`
- Frames con `confidence >= 0.5`: `804`
- Detection rate aparente: `84.72%`
- Confidence media: `0.746542`
- Overlay: `1920x1080`, `60 fps`, `15.816667 s`

Detection rate aparente no equivale a ground truth formal; el cierre de esta etapa se basa en validacion visual humana.

## Limitaciones conocidas

Se observaron 4 errores/desvios puntuales, principalmente en momentos de impacto del jugador far/lejos de la camara. En esos frames, el marcador puede separarse de la pelota real o perder trazabilidad local.

No se interpreta como falla global de WASB. No se pivota a otro modelo, no se instala TrackNetV3 y no se hace fine-tuning.

## Handoff a Stage 3

Stage 3 debe consumir:

- `data/reference_clip/wasb_detections.csv`
- `data/reference_clip/homography.json`

Stage 3 debe absorber explicitamente los errores puntuales observados mediante:

- suavizado temporal;
- rechazo de outliers;
- interpolacion de gaps cortos;
- control de discontinuidades entre frames;
- deteccion de saltos fisicamente incoherentes.

Si Stage 3 no logra absorber los 4 desvios puntuales, Stage 2 se reabrira solo para revisar thresholds, frames clave o preprocesado. No se cambia de modelo sin decision explicita del usuario.
