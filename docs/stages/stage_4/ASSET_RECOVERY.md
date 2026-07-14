# Recuperacion de assets - Stage 4

**Estado local auditado:** faltan los artefactos ignorados requeridos para el run real.

## Minimo para continuar Stage 4

Copiar desde la maquina original a estas rutas exactas del Mac:

```text
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/stage_3/smoothed_trajectory.csv
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/data/reference_clip/madrid_R1.mov
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/outputs/stage_3/smoothed_trajectory_overlay.mp4
```

Crear o completar humanamente:

```text
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/data/reference_clip/manual_annotation.json
```

`data/reference_clip/homography.json` ya esta presente y versionado.

El CSV suavizado es el output aceptado de Stage 3. El video y overlay permiten ubicar y
validar eventos. `manual_annotation.json` debe provenir de una persona; no existe una
ruta automatica aprobada para Nivel A.

## Respaldo recomendado de reproducibilidad

Si siguen disponibles, conservar tambien fuera de Git:

```text
data/reference_clip/reference_frame.png
data/reference_clip/wasb_detections.csv
outputs/stage_2/wasb_detections_overlay.mp4
outputs/stage_3/trajectory_debug_overlay.mp4
outputs/stage_3/trajectory_quality_report.json
models/wasb/wasb_tennis_best.pth.tar
third_party/WASB-SBDT/
```

No copiar `.venv` entre WSL/Windows y macOS. No instalar tracker ni intentar regenerar
Stage 2/3 en macOS Intel como parte de esta recuperacion.

## Integridad de la transferencia

En la maquina de origen, generar un manifiesto antes de copiar:

```bash
shasum -a 256 outputs/stage_3/smoothed_trajectory.csv \
  data/reference_clip/madrid_R1.mov \
  outputs/stage_3/smoothed_trajectory_overlay.mp4
```

Repetir el mismo comando en el Mac y comparar los hashes. Los assets siguen ignorados por
Git y no deben agregarse a un commit.

## Verificacion posterior

```bash
test -f outputs/stage_3/smoothed_trajectory.csv
test -f outputs/stage_3/smoothed_trajectory_overlay.mp4
test -f data/reference_clip/madrid_R1.mov
test -f data/reference_clip/manual_annotation.json
uv run python -m src.events.event_loader
```

Despues deben generarse timeline y overlay y solicitarse el gate humano. Stage 5 sigue
bloqueada hasta que ese gate se apruebe.
