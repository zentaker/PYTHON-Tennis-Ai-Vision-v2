# Exit Report - Stage 1

**Estado:** Cerrada exitosa  
**Fecha de inicio:** 2026-05-18  
**Fecha de cierre:** 2026-05-18  
**Nivel:** A

## Resumen

Stage 1 produjo la calibración de cancha para el clip Nivel A usando 8 puntos manuales capturados por clic en navegador web local. La homografía píxel -> cancha quedó persistida y validada numéricamente. El usuario firmó el gate visual 1.7 tras revisar la reproyección de líneas sobre el frame.

## Artefactos principales

- `data/reference_clip/reference_frame.png`
- `data/reference_clip/court_corners_pixel.json`
- `data/reference_clip/homography.json`
- `outputs/stage_1/calibration_guide.png`
- `outputs/stage_1/reprojection_error_report.json`
- `outputs/stage_1/court_2d_top.png`
- `outputs/stage_1/reference_frame_with_reprojected_court.png`

## Métricas de homografía

- Método: `cv2.findHomography(method=0)`
- Modo de cancha: `doubles`
- Error medio court->pixel: `2.3969369839150216 px`
- Error máximo court->pixel: `4.840169152421834 px`
- Error medio pixel->court: `0.060892341675991835 m`
- Error máximo pixel->court: `0.12152420090899765 m`
- DoD numérico: aprobado (`mean < 5 px`, `max < 15 px`)

## Horas totales invertidas

Estimación activa: `1.7 h`.

Base de estimación:

- Carry-over Stage 0: `~10 min`
- 1.0 pre-condiciones: `~5 min`
- 1.1-1.3 preparación inicial: `~25 min`
- 1.3 fallback web local: `~25 min`
- 1.4-1.6 homografía, validación y renders: `~35 min`

## Horas de fricción

Fricción Stage 1 y carry-over asociado: `0.4 h`.

Entradas consideradas:

- `F-0003`: `0.1 h`
- `F-0004`: `0.0 h`
- `F-0005`: `0.1 h`
- `F-0006`: `0.2 h`

## Ratio de fricción

```text
ratio_friccion = 0.4 / 1.7 = 0.24
```

Lectura: fricción moderada, con lecciones documentadas.

## Fricciones registradas

- `F-0003` - DOC - aceptación formal pendiente de ADR-0001 a ADR-0005. Resuelta.
- `F-0004` - DOC - assets de clip pendientes de verificación. Resuelta.
- `F-0005` - DEP - `ffmpeg` no instalado; frame extraído con OpenCV; instalación raíz pendiente por `sudo`. Abierta, no bloqueante para Stage 1.
- `F-0006` - ENV - WSLg/Qt no pudo abrir `cv2.imshow`; fallback web usado. Resuelta operativamente, deuda técnica para Stages 5/6.

## Lecciones aprendidas

- WSLg/Qt es deuda técnica documentada en `F-0006`, pendiente para Stages 5/6.
- El método de captura por clic en navegador web local funcionó y reemplazó al modo "coordenadas a mano" que era inviable. Documentado en `ADR-0008`.
- `sudo` password no se persistió: `ffmpeg` quedó como deuda en `F-0005`, no bloqueante.
- Para puntos manuales cuidadosamente capturados, `cv2.findHomography(method=0)` fue suficiente y evita esconder errores de click mediante RANSAC.

## Cambios al roadmap

No hubo cambios al roadmap. Stage 1 se mantuvo dentro del alcance de geometría y calibración; no se avanzó a detección, tracking ni modelos.

## Recomendación ADR-0007

`ADR-0007` debe revisarse antes de iniciar trabajo pesado de Stage 2. Recomendación: hacer el review obligatorio al inicio de Stage 2, antes del primer test real de inferencia de WASB, pero no migrar todavía. La decisión debe basarse en la prueba que importa para Stage 2: si WASB corre el clip en menos de 10 minutos. Si el primer benchmark apunta a cuello de botella serio por `/mnt/c`, migrar a WSL home antes de invertir más trabajo.

## Aprobación humana

Gate 1.7 firmado visualmente por el usuario el 2026-05-18. Líneas reproyectadas caen correctamente sobre las líneas reales del clip en toda la cancha.

## Estado final

Stage 1 queda cerrado exitosamente. No iniciar Stage 2 sin prompt explícito del usuario y sin revisar `ADR-0007` según su mitigación.
