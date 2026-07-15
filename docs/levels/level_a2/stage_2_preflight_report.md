# Reporte de preflight Stage 2 — Nivel A2

**Fecha:** 2026-07-14

**Resultado:** `PASS_WITH_WARNINGS`

El preflight de datos y geometría pasa completamente. Las advertencias son la ausencia
local del checkpoint y de WASB-SBDT, que son requisitos de la futura máquina GPU y no se
descargaron en macOS. No se ejecutó inferencia ni se generaron detecciones.

## Comando ejecutado

```bash
uv run python scripts/stage2_a2_preflight.py \
  --video data/clips/nivel_a2_01/source.mp4 \
  --manifest data/clips/nivel_a2_01/clip_manifest.json
```

## Resultado técnico

| Verificación | Resultado |
| --- | --- |
| Estado interno | `LIGHTWEIGHT_PREFLIGHT_PASSED` |
| SHA-256 MP4 | `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774` |
| Manifest / homografía | Legibles y coherentes con `nivel_a2_01` |
| Frames manifest/OpenCV/decodificados | `527 / 527 / 527` |
| IDs | Secuenciales, `0–526` |
| Muestras | Frames `0`, `263` y `526` legibles |
| Backend temporal | `/usr/local/bin/ffprobe`, FFmpeg `8.1.2` |
| Rango de timestamps | `0.000000–10.471667 s` |
| Timestamps | Monotónicos y coincidentes con la decodificación |
| Intervalos observados | `0.016666`, `0.016667`, `0.021667`, `0.033334 s` |
| Timing | VFR confirmado; sin conversión a CFR |
| Entrada decodificada | `1536x2746` |
| Transformación | `rotate_90_ccw` |
| Salida canónica | `2746x1536` en los 527 frames |
| Doble rotación | Prevenida al reingresar un frame ya canónico |
| PyTorch/WASB | No importados ni ejecutados |

La diferencia entre el último PTS (`10.471667 s`) y la duración de contenedor incluye la
duración del frame final; no implica pérdida de frames. FFprobe expone más precisión de
PTS que el fallback previo de OpenCV.

## Rutas previstas

- CSV: `data/clips/nivel_a2_01/wasb_detections.csv`.
- Overlay: `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.
- Reporte real: `outputs/nivel_a2_01/stage_2/inference_report.json`.

Ninguna de estas rutas fue creada durante el preflight.

## Inventario WASB

| Artefacto | Estado | Tamaño | SHA-256 | Uso |
| --- | --- | ---: | --- | --- |
| `models/wasb/wasb_tennis_best.pth.tar` | MISSING | — | — | Ejecución GPU |
| `third_party/WASB-SBDT` | MISSING | — | — | Ejecución GPU |
| `data/clips/nivel_a2_01/wasb_detections.csv` | MISSING | — | — | Gate posterior |
| `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4` | MISSING | — | — | Gate posterior |

El checkpoint y WASB-SBDT deben recuperarse del entorno Windows/WSL RTX usado para la
pasada histórica, de su backup autorizado o de la fuente upstream autorizada en la nueva
máquina GPU. No se descargaron automáticamente.

## Riesgos abiertos

- MP4 HEVC y soporte de codec en el entorno externo.
- Resolución alta `2746x1536`.
- Cadencia VFR y PTS no uniformes.
- Pelota pequeña frente a la resolución completa.
- Metadata de rotación `270°`; cualquier bypass del frame canónico invalidaría las
  coordenadas.
- Compatibilidad checkpoint/WASB/PyTorch/CUDA aún no comprobada.

## Decisión

El preflight A2 queda aprobado con advertencias de runtime. Stage 2 permanece pendiente
de ejecución externa y gate visual. Stage 3 A2 no puede comenzar todavía.
