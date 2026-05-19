# Trajectory Smoothing Report - Stage 3

**Fecha:** 2026-05-19  
**Nivel:** A  
**Estado:** listo para validacion visual humana

## Objetivo

Stage 3 convierte las detecciones crudas de WASB en una trayectoria temporalmente suavizada, robusta a falsos positivos aislados, gaps cortos y saltos visualmente incoherentes.

Esta etapa no cambia de modelo, no regenera WASB, no hace fine-tuning y no detecta eventos. Tampoco inicia Stage 4.

## Inputs usados

- `data/reference_clip/wasb_detections.csv`
- `data/reference_clip/madrid_R1.mov`
- `data/reference_clip/homography.json`

## Metodo

Se implemento un suavizado 2D en coordenadas de imagen con reglas simples y explicables:

1. Umbral de confianza para separar detecciones candidatas de frames missing.
2. Rechazo de spikes aislados usando ventana local.
3. Rechazo de saltos fisicamente incoherentes por velocidad maxima en pixeles/frame.
4. Interpolacion lineal de gaps cortos.
5. Media movil centrada dentro de segmentos continuos validos.

Se eligio este enfoque antes que un Kalman filter para mantener Stage 3 simple, auditable y facil de ajustar. Kalman queda como mejora posible si el gate visual humano no pasa.

## Parametros

- `threshold_min`: `0.5`
- `max_gap_frames`: `10`
- `max_jump_px`: `220.0`
- `local_window`: `7`
- `isolated_outlier_px`: `140.0`
- `smoothing_window`: `5`

## Outputs locales

Rutas Windows para revision:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory.csv
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_debug_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_quality_report.json
```

Rutas WSL:

```text
/mnt/c/Users/MSI/Desktop/TennisAI/outputs/stage_3/smoothed_trajectory.csv
/mnt/c/Users/MSI/Desktop/TennisAI/outputs/stage_3/smoothed_trajectory_overlay.mp4
/mnt/c/Users/MSI/Desktop/TennisAI/outputs/stage_3/trajectory_debug_overlay.mp4
/mnt/c/Users/MSI/Desktop/TennisAI/outputs/stage_3/trajectory_quality_report.json
```

Los outputs son locales e ignorados por Git por diseno.

## Metricas finales

- Frames totales: `949`
- Frames `detected`: `801`
- Frames `rejected`: `3`
- Frames `interpolated`: `95`
- Frames `missing`: `50`
- Cobertura final: `899 / 949`
- Cobertura final porcentual: `94.73%`
- Saltos rechazados: `3`
- Gaps interpolados: `39`
- Maximo gap interpolado: `9`

Frames rechazados automaticamente:

| Frame | Motivo |
|---:|---|
| 202 | `isolated_spike|filled_by_interpolation` |
| 329 | `isolated_spike|filled_by_interpolation` |
| 545 | `isolated_spike|filled_by_interpolation` |

## Metadata de overlays

Ambos overlays fueron generados y OpenCV pudo abrir el primer frame.

- Resolucion: `1920x1080`
- FPS: `60`
- Frames: `949`

## Relacion con los 4 errores observados en Stage 2

El usuario observo 4 errores/desvios puntuales en el overlay crudo de Stage 2, principalmente en impactos del jugador far/lejos de la camara.

Esta primera version de Stage 3 rechazo automaticamente 3 spikes aislados. El cuarto caso debe revisarse visualmente:

- puede haber sido absorbido por el suavizado/interpolacion sin disparar regla de rechazo;
- o puede requerir ajuste de parametros si sigue visible en el overlay suavizado.

No se interpreta esto como razon para cambiar de modelo. La revision debe enfocarse en parametros de Stage 3.

## Como revisar el gate

Abrir primero:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
```

Si hay duda, abrir:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_debug_overlay.mp4
```

El overlay debug muestra punto crudo, punto suavizado, `confidence`, `source` y razon de rechazo/interpolacion.

## Limitaciones

- El suavizado es 2D en pixeles; no usa aun fisica 3D.
- No detecta botes ni golpes.
- No usa homografia para decidir outliers.
- Los gaps mayores a 10 frames quedan missing.
- Los frames rechazados pueden recibir coordenadas suavizadas si estan dentro de un gap corto interpolable.

## Veredicto pendiente

Stage 3 no queda cerrada automaticamente. Requiere veredicto visual humano:

- `A`: trayectoria suavizada aceptable.
- `B`: trayectoria suavizada peor/no sirve.
- `C`: dudoso, requiere ajuste de parametros.

## Refinamiento tras validacion humana

Veredicto humano inicial sobre el primer overlay de Stage 3:

```text
C) aceptable en general, pero con 2 artefactos visibles que deben corregirse antes de cerrar.
```

Artefactos observados:

- Cerca del saque / bote del saque: aparecia un segmento diagonal largo o fisicamente poco creible.
- Cerca de una derecha del jugador far/lejos de la camara: aparecia una trayectoria rara alrededor del impacto.

Regla agregada:

- Segunda pasada `local_prediction_break`.
- Rechaza puntos que rompen un puente local coherente entre vecinos validos.
- No rechaza solo por velocidad; requiere salto grande + baja coherencia local + alto error contra prediccion lineal.

Parametros nuevos:

- `residual_prediction_px`: `120.0`
- `residual_neighbor_jump_px`: `135.0`

Metricas antes/despues:

| Metrica | Antes | Despues |
|---|---:|---:|
| Frames totales | 949 | 949 |
| Detected | 801 | 799 |
| Rejected | 3 | 5 |
| Interpolated | 95 | 95 |
| Missing | 50 | 50 |
| Cobertura final | 899 / 949 (94.73%) | 899 / 949 (94.73%) |
| Saltos rechazados iniciales | 3 | 3 |
| Segmentos anomalos residuales detectados | 0 | 2 |
| Gaps interpolados | 39 | 40 |
| Maximo gap interpolado | 9 | 9 |
| Maximo salto frame-a-frame | 73.717790 px | 35.363514 px |

Nuevos frames rechazados:

- `81`: `local_prediction_break|filled_by_interpolation`
- `132`: `local_prediction_break|filled_by_interpolation`

Artefactos de revision generados:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\anomaly_candidates.csv
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\before_after_contact_sheet.png
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\refined_overlay_excerpt.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\top_jump_frames\
```

Nuevo gate pendiente:

Revisar el overlay refinado:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
```

Si persiste duda, revisar el overlay debug y el contact sheet antes/despues. Stage 3 sigue pendiente de validacion humana y Stage 4 no se inicia.
