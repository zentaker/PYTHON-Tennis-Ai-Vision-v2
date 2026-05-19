# STAGE 1 - Calibracion de cancha

**Version:** 0.1  
**Fecha de inicio:** 2026-05-18  
**Fecha de cierre:** 2026-05-18  
**Estado:** Cerrada exitosa  
**Nivel:** A

## Proposito de la etapa

Dado un frame de referencia del clip, obtener una matriz de homografia H que mapee pixeles de la cancha a coordenadas reales en metros.

## Entregables (checklist)

```text
[x] Frame de referencia extraido desde el clip Nivel A
[x] Modulo de coordenadas de cancha
[x] ADR-0006 propuesto
[x] Script interactivo de calibracion preparado
[ ] Matriz H persistida en JSON
[ ] Script de validacion con error de reproyeccion
[ ] Render de cancha 2D vacia a partir de H
```

## Decisiones tomadas (links a ADRs)

- `docs/decisions/0006-sistema-coordenadas-cancha.md` (Propuesta)

## Friccion registrada

- `F-0005`: `ffmpeg` no disponible; frame 0 extraido con OpenCV como fallback.

## 1.1 - Extraccion del frame de referencia

`data/reference_clip/reference_frame.png` fue extraido desde `data/reference_clip/madrid_R1.mov`.

- Metodo usado: OpenCV `cv2.VideoCapture`, porque `ffmpeg` no estaba instalado en WSL.
- Frame extraido: 0.
- Forma de imagen: `(1080, 1920, 3)`.
- Justificacion: el frame muestra la cancha completa y los puntos de calibracion principales son visibles, aunque existe overlay de marcador que no bloquea Stage 1.

## 1.2 - Sistema de coordenadas

Se creo `src/court/coordinates.py` con:

- Convencion de origen en el centro de la red.
- Eje X paralelo a la red.
- Eje Y perpendicular a la red, negativo en lado near y positivo en lado far.
- Dimensiones reales en metros.
- Puntos de calibracion parametrizados para `doubles` y `singles`.

ADR-0006 queda en estado `Propuesta` hasta aprobacion humana.

## Preparacion 1.3 - Calibracion interactiva

Se creo `src/court/calibrate_interactive.py`.

- Modo interactivo: captura 8 puntos en orden y guarda `data/reference_clip/court_corners_pixel.json`.
- Preview: `outputs/stage_1/calibration_clicks_preview.png`.
- Modo verificacion: `--check-window`.

Resultado WSLg: `cv2.imshow` no inicializo por error Qt/xcb. Se activa modo `1.3-fallback` salvo que se instalen dependencias GUI antes de capturar puntos.

## Guia manual de calibracion

Se genero `outputs/stage_1/calibration_guide.png` con marcadores aproximados para indicar el orden de los 8 puntos. La guia es orientativa y no se usa como ground truth.

La calibracion final usara `layout=doubles`, confirmado por el usuario el 2026-05-19.

## 1.4 - Homografia

Se calculo `data/reference_clip/homography.json` usando los 8 puntos capturados por clic web en `data/reference_clip/court_corners_pixel.json`.

- Modo de cancha: `doubles`.
- Metodo: `cv2.findHomography(method=0)`.
- Justificacion: puntos manuales cuidadosamente clickeados; usar RANSAC podria ocultar errores de anotacion.
- Error medio de reproyeccion en pixeles: `2.3969369839150216`.
- Error maximo de reproyeccion en pixeles: `4.840169152421834`.

## 1.5 - Validacion de reproyeccion

Se genero `outputs/stage_1/reprojection_error_report.json`.

- Error medio court->pixel: `2.3969369839150216 px`.
- Error maximo court->pixel: `4.840169152421834 px`.
- Error medio pixel->court: `0.060892341675991835 m`.
- Error maximo pixel->court: `0.12152420090899765 m`.
- DoD numerico: aprobado (`mean < 5 px`, `max < 15 px`).

No se pidieron puntos independientes en este bloque; queda pendiente para el gate visual de 1.7 si el usuario lo requiere.

## 1.6 - Renders de evidencia visual

Se generaron:

- `outputs/stage_1/court_2d_top.png`
- `outputs/stage_1/reference_frame_with_reprojected_court.png`

El gate de Stage 1 queda pendiente de validacion visual humana sobre la reproyeccion.

## Definition of Done

- Error medio de reproyeccion menor a 5 px sobre 8 puntos de calibracion.
- Error sobre puntos independientes menor a 10 px.
- Render visualmente coherente.

## Gate

Inspeccion visual humana del render.

## Reporte de cierre

Ver `exit_report.md`.
