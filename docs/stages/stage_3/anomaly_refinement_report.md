# Anomaly Refinement Report - Stage 3

**Fecha:** 2026-05-19  
**Estado:** segundo refinamiento implementado, pendiente de nueva validacion visual humana

## Contexto

El usuario reviso el primer overlay de Stage 3 y emitio veredicto inicial:

```text
C) aceptable en general, pero con 2 artefactos visibles que deben corregirse antes de cerrar.
```

Artefactos observados:

1. Cerca del saque / bote del saque: segmento diagonal largo o fisicamente poco creible.
2. Cerca de una derecha del jugador far/lejos de la camara: trayectoria rara alrededor del impacto.

La interpretacion operativa es que Stage 3 no fallo globalmente. Se requiere un refinamiento quirurgico de rechazo de outliers/interpolacion, no cambio de modelo.

## Analisis numerico previo

Sobre `outputs/stage_3/smoothed_trajectory.csv` se calcularon:

- distancia entre puntos consecutivos;
- velocidad px/frame;
- aceleracion aproximada;
- cambios bruscos de direccion;
- top segmentos largos;
- top aceleraciones.

Senales principales antes del refinamiento:

- Maximo salto frame-a-frame: `73.717790 px`, segmento `134 -> 135`.
- Top aceleraciones concentradas cerca de `129-135`.
- Artefacto residual adicional identificado por coherencia local en frame `81`.
- El frame `329` ya estaba marcado como `rejected` por la primera version, consistente con la zona de impacto far observada desde Stage 2.

Frames candidatos relevantes:

| Frame | Motivo |
|---:|---|
| 81 | Punto crudo con alta desviacion local cerca de la trayectoria del saque; rompe puente local coherente. |
| 132 | Punto crudo aceptado cerca del saque/bote que produce artefacto diagonal visible. |
| 329 | Spike de zona far ya rechazado por la primera version; se mantiene como candidato de revision visual. |
| 134-135 | Maximo salto frame-a-frame antes del refinamiento, asociado al artefacto de saque/bote. |

## Regla agregada

Se agrego una segunda pasada general llamada `local_prediction_break`.

La regla rechaza un punto cuando:

- existe un punto valido anterior y uno posterior dentro de una ventana local;
- el puente anterior -> posterior es coherente;
- el punto actual se aleja mucho de la prediccion lineal entre ambos;
- los dos segmentos hacia el punto actual son grandes.

Parametros nuevos:

- `residual_prediction_px`: `120.0`
- `residual_neighbor_jump_px`: `135.0`

Esta regla no rechaza solo por velocidad, porque la pelota puede moverse rapido. Rechaza cuando hay salto grande + baja coherencia local + ruptura de prediccion entre vecinos.

## Resultado del refinamiento

Nuevos frames rechazados:

| Frame | Motivo nuevo |
|---:|---|
| 81 | `local_prediction_break|filled_by_interpolation` |
| 132 | `local_prediction_break|filled_by_interpolation` |

Frames previamente rechazados que se mantienen:

| Frame | Motivo |
|---:|---|
| 202 | `isolated_spike|filled_by_interpolation` |
| 329 | `isolated_spike|filled_by_interpolation` |
| 545 | `isolated_spike|filled_by_interpolation` |

## Metricas antes/despues

| Metrica | Antes | Despues |
|---|---:|---:|
| Frames totales | 949 | 949 |
| Detected | 801 | 799 |
| Rejected | 3 | 5 |
| Interpolated | 95 | 95 |
| Missing | 50 | 50 |
| Cobertura final | 899 / 949 (94.73%) | 899 / 949 (94.73%) |
| Saltos rechazados iniciales | 3 | 3 |
| Anomalias residuales detectadas | 0 | 2 |
| Gaps interpolados | 39 | 40 |
| Maximo gap interpolado | 9 | 9 |
| Maximo salto frame-a-frame | 73.717790 px | 35.363514 px |

## Artefactos locales de revision

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\anomaly_candidates.csv
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\before_after_contact_sheet.png
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\refined_overlay_excerpt.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\top_jump_frames\
```

Outputs refinados principales:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_debug_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory.csv
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_quality_report.json
```

## Segundo refinamiento: artefacto residual segundo 12

Tras revisar el primer refinamiento, el usuario confirmo:

- El artefacto del saque quedo corregido.
- Permanece un unico artefacto residual alrededor del segundo 12.
- El problema se ve en el lado far / jugador lejano como una mala continuidad local.

Rango analizado:

- Prioritario: frames `700-740`
- Expandido: frames `680-760`

Hallazgo:

| Frame | Antes | Despues | Motivo |
|---:|---|---|---|
| 745 | `detected` | `rejected` | Punto de baja confidence relativa (`0.547193`) que rompe el puente local entre frames vecinos coherentes. |

Detalle del frame responsable:

```text
frame_id: 745
raw: (750.0, 183.75)
smooth antes: (744.0, 129.75)
smooth despues: (742.5, 116.25)
reason despues: low_confidence_prediction_break|filled_by_interpolation
```

Regla adicional aplicada:

- `low_confidence_prediction_break`
- Se activa solo para puntos que pasaron el threshold minimo pero tienen confidence baja relativa.
- Requiere desviacion contra prediccion local + saltos a vecinos, no velocidad sola.

Parametros nuevos:

- `low_confidence_break_max_conf`: `0.6`
- `low_confidence_prediction_px`: `55.0`
- `low_confidence_neighbor_jump_px`: `50.0`

Metricas antes/despues del segundo refinamiento:

| Metrica | Antes segundo refinamiento | Despues segundo refinamiento |
|---|---:|---:|
| Detected | 799 | 798 |
| Rejected | 5 | 6 |
| Interpolated | 95 | 95 |
| Missing | 50 | 50 |
| Cobertura final | 899 / 949 (94.73%) | 899 / 949 (94.73%) |
| Anomalias residuales detectadas | 2 | 3 |
| Gaps interpolados | 40 | 41 |
| Maximo gap interpolado | 9 | 9 |

Artefactos focalizados:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\second12_anomaly_window.csv
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\second12_debug_excerpt.mp4
```

## Gate pendiente

El usuario debe revisar nuevamente:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\smoothed_trajectory_overlay.mp4
```

Y, si necesita diagnostico visual:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\trajectory_debug_overlay.mp4
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\before_after_contact_sheet.png
C:\Users\MSI\Desktop\TennisAI\outputs\stage_3\refinement_review\refined_overlay_excerpt.mp4
```

Stage 3 sigue pendiente de gate humano. No se inicio Stage 4.
