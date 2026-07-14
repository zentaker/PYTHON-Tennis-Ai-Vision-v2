# Validación de orientación — Stage 1 Nivel A2

**Clip:** `nivel_a2_01`

**Fecha:** 2026-07-14

**Resultado técnico:** correcto

**Gate:** aprobado por validación visual humana

## Espacio canónico

El MP4 conserva metadata de rotación de contenedor de `270°`. Una lectura directa con
OpenCV puede producir frames laterales de `1536x2746`; esas coordenadas no son compatibles
con esta calibración.

El frame 180 aprobado fue normalizado una sola vez a orientación horizontal. Toda la
captura de Stage 1 y la homografía corresponden exclusivamente al frame canónico de
`2746x1536`:

- frame: `data/clips/nivel_a2_01/reference_frame.png`;
- corners: `data/clips/nivel_a2_01/court_corners_pixel.json`;
- homografía: `data/clips/nivel_a2_01/homography.json`.

## Comprobaciones

| Comprobación | Evidencia | Resultado |
| --- | --- | --- |
| Frame horizontal | width `2746`, height `1536` | Pasa |
| Bounds | Los ocho puntos están dentro de `2746x1536` | Pasa |
| Far/near | Los cuatro puntos `far` tienen menor `y` que sus pares `near` | Pasa |
| Left/right | Los cuatro puntos `left` tienen menor `x` que sus pares `right` | Pasa |
| Rotación del overlay | Baselines horizontales, sidelines en profundidad y red transversal | Pasa |
| Reproyección | Media `4.705469 px`, máximo `8.598912 px` | Pasa |

La inspección del overlay no muestra una reproyección rotada 90°, ni intercambio entre
izquierda/derecha o fondo/cercanía. El usuario aprobó visualmente el archivo:

`outputs/nivel_a2_01/stage_1/reference_frame_with_reprojected_court.png`

## Contrato para etapas posteriores

Stage 2 deberá usar exactamente la misma orientación antes de producir coordenadas:

`raw video frame -> canonical orientation 2746x1536 -> detector coordinates -> homography`

Cualquier detección WASB obtenida en el espacio lateral `1536x2746` deberá transformarse
al espacio canónico antes de aplicar esta homografía. Esta regla queda implementada para
la preparación de Stage 2, pero WASB todavía no se ha ejecutado.
