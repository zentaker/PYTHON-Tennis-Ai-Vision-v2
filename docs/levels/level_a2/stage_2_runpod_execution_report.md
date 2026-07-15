# Reporte de ejecución RunPod — Stage 2 A2

**Fecha:** 2026-07-15  
**Estado:** `TECHNICALLY_EXECUTED_PENDING_HUMAN_VISUAL_GATE`

## Resultado final

La conexión SSH directa, el bootstrap y el preflight terminaron correctamente. La
inferencia WASB se ejecutó una vez en CUDA y produjo los tres artefactos esperados. El
estado histórico `BLOCKED_CONNECTION` queda reemplazado por este resultado real.

No se considera cerrada Stage 2: falta revisar visualmente el overlay completo.

## Entorno y procedencia

- Repositorio remoto: `/workspace/PYTHON-Tennis-Ai-Vision-v2`.
- Commit exacto: `421fe01a3721ffcdc38f89a37316a9277797e5f3`.
- GPU: NVIDIA RTX A5000.
- VRAM: `24,564 MiB`.
- Driver NVIDIA: `580.159.04`.
- CUDA: `13.0`; PyTorch `2.12.0+cu130`; `torch.cuda.is_available() = true`.
- WASB-SBDT commit: `923462cacdeb3353b84ddebdedb3f4b7a8553b0f`.
- Checkpoint: `models/wasb/wasb_tennis_best.pth.tar`, `6,102,633` bytes.
- SHA-256 checkpoint:
  `9d391239ab10c733f8e5bfadf16ab72838e7a8ebc88e8ae2038501c03d42b4bb`.
- Bootstrap: OK.
- Preflight: OK, incluidos `527/527` frames, timeline VFR monótona y orientación
  canónica.

El log final local es
`outputs/nivel_a2_01/stage_2/logs/stage2_20260715T071607Z_421fe01a3721.log`.
`inference_report.json` registra commit, GPU, CUDA y frames, pero no incorpora campos
propios para los SHA del video/checkpoint ni para el commit de WASB-SBDT; esos datos se
reconcilian con el preflight y el inventario de activos de la ejecución, sin reescribir
el reporte generado.

## Input verificado

- Video: `data/clips/nivel_a2_01/source.mp4`.
- Tamaño: `24,944,366` bytes.
- SHA-256:
  `e2a05a8eda9be4d821ae1acc60355c7c0403e450ac0febd6bb3c6a62e0aa5774`.
- Timeline: `527` timestamps, IDs `0–526`, estrictamente monótonos.
- Orientación canónica: `2746x1536`, transformación `rotate_90_ccw`.

## Ejecución y artefactos

- Frames procesados: `527/527`.
- Registros CSV: `527`.
- Tiempo de inferencia: `50.849159 s` (`10.363986 fps`).
- Device: `cuda`.
- CSV: `data/clips/nivel_a2_01/wasb_detections.csv`.
- Overlay: `outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4`.
- Reporte: `outputs/nivel_a2_01/stage_2/inference_report.json`.
- Overlay validado: `527` frames, `2746x1536`, duración `10.471668 s`, legible por
  FFprobe y OpenCV.

## Resumen técnico de detecciones

- `detected=true`: `383/527` (`72.6755%`).
- Confidence media: `0.651804`; mediana: `0.839530`.
- Percentiles confidence: p10 `0.052530`, p25 `0.272923`, p75 `0.896439`, p90
  `0.926728`.
- Gaps consecutivos sin detección: `12`.
- Gap máximo: frames `0–80`, `81` frames, span de timestamps `1.588333 s`.
- Frames de menor confidence: `1, 15, 14, 17, 11, 16, 6, 3, 8, 4`.
- Mayores saltos crudos entre detecciones:
  - `351→363`: `207.234 px`, `828.936 px/s`;
  - `435→436`: `75.849 px`, `4550.820 px/s`;
  - `487→505`: `65.247 px`, `177.946 px/s`;
  - `287→288`: `61.151 px`, `1834.499 px/s`;
  - `288→289`: `60.678 px`, `3640.840 px/s`.

Las distancias y velocidades son métricas técnicas; no prueban por sí solas que el
punto siga visualmente la pelota.

## Gate pendiente

Stage 2 queda ejecutada técnicamente, no cerrada. Una persona debe revisar
`outputs/nivel_a2_01/stage_2/wasb_detections_overlay.mp4` y emitir el gate visual. Stage
3 no fue ejecutada en el Pod y Stage 4/5 no fueron iniciadas.
