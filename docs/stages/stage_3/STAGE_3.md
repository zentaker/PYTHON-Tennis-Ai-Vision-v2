# STAGE 3 - Trayectoria temporalmente suavizada

**Estado:** Preparada, no iniciada  
**Nivel:** A  
**Fecha de preparacion:** 2026-05-19

## Proposito

Convertir las detecciones crudas de WASB en una trayectoria continua y fisicamente plausible de la pelota, robusta a falsos positivos puntuales y frames con deteccion debil o perdida.

Esta etapa no esta implementada todavia. Este documento solo prepara el handoff desde Stage 2.

## Entradas iniciales

Stage 3 empieza desde:

- `data/reference_clip/wasb_detections.csv`
- `data/reference_clip/homography.json`

Entradas auxiliares disponibles:

- `data/reference_clip/madrid_R1.mov`
- `outputs/stage_2/wasb_detections_overlay.mp4`
- `docs/stages/stage_2/exit_report.md`

## Problemas que debe atender

Stage 2 fue cerrado como visualmente viable, pero con limitaciones conocidas. Stage 3 debe atender explicitamente:

- outliers aislados en momentos de impacto;
- gaps cortos;
- discontinuidades entre frames;
- rechazo de detecciones fisicamente incoherentes;
- interpolacion en tramos cortos.

La observacion humana clave heredada de Stage 2 es:

```text
Se observaron 4 errores/desvios puntuales, principalmente en momentos de impacto del jugador far/lejos de la camara.
```

## Alcance previsto

Entregables esperados cuando Stage 3 se implemente:

- CSV de trayectoria suavizada con columnas derivadas de deteccion cruda.
- Campo `source` con valores como `detected`, `interpolated` o `rejected`.
- Overlay de trayectoria suavizada para validacion visual.
- Reporte de cierre con veredicto humano.

## Criterios preliminares de exito

- Cero discontinuidades visibles en la trayectoria final.
- Saltos entre frames consecutivos coherentes con velocidad fisica plausible.
- Los errores puntuales observados en Stage 2 quedan rechazados o absorbidos sin romper la trayectoria.
- Los gaps cortos se interpolan sin crear saltos visuales.

## Reglas de la etapa

- No cambiar de modelo durante Stage 3.
- No instalar TrackNetV3.
- No hacer fine-tuning.
- No reabrir Stage 2 salvo que el suavizado no pueda absorber los errores puntuales documentados.
- No avanzar a Stage 4 hasta que la trayectoria suavizada pase validacion visual humana.

## Estado actual

Stage 3 queda documentada y lista para recibir un prompt especifico de implementacion. No se implemento codigo de Stage 3 en esta sesion.
