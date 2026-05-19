# Local Continuity Audit - Stage 2

**Fecha/hora:** 2026-05-19, America/Lima  
**Ruta canonica Windows:** `C:\Users\MSI\Desktop\TennisAI`  
**Ruta canonica WSL:** `/mnt/c/Users/MSI/Desktop/TennisAI`  
**Objetivo:** auditar continuidad local despues de actualizar GitHub, sin migrar, regenerar ni avanzar a Stage 3.

## Estado Git

- Rama actual: `main`
- Remoto: `origin https://github.com/zentaker/PYTHON-Tennis-Ai-Vision-v2.git`
- HEAD local: `98c645808326af6501e5acbf86d7dbbf35a54a29`
- HEAD `origin/main`: `98c645808326af6501e5acbf86d7dbbf35a54a29`
- Estado: limpio, `main...origin/main`
- Ultimos commits relevantes:
  - `98c6458 stage2(viability): wasb inference produced overlay for visual verdict`
  - `d30de58 stage2(adr-0007): accept /mnt/c per user decision, close F-0007`
  - `3f5558c stage2(setup): add WASB tracker dependencies`

Conclusion Git: el repo local coincide con GitHub. No hay merge, reset, rebase ni recuperacion pendiente.

## Resumen relevante de .gitignore

El repo esta disenado para versionar codigo, docs, ADRs, scripts y estructura; no artefactos pesados.

Ignorado por diseno:

- `outputs/*`
- `models/*`
- `third_party/`
- `data/*`, con excepciones explicitas
- `data/reference_clip/*`, con excepciones para `README.md`, `court_corners_pixel.json`, `homography.json`, `manual_annotation.json` y `manual_annotation.example.json`
- Videos: `*.mov`, `*.mp4`, `*.avi`, `*.mkv`, `*.webm`, `*.wmv`, `*.flv`, `*.m4v`, `*.ts`
- Pesos/checkpoints: `*.pth`, `*.pt`, `*.ckpt`, `*.h5`, `*.onnx`, `*.tflite`, `*.safetensors`, `*.bin`, `*.npz`, `*.npy`, `*.parquet`

Confirmaciones via `git check-ignore`:

- `outputs/stage_2/wasb_detections_overlay.mp4` ignorado por `outputs/*`
- `data/reference_clip/wasb_detections.csv` ignorado por `data/reference_clip/*`
- `models/wasb/wasb_tennis_best.pth.tar` ignorado por `models/*`
- `third_party/WASB-SBDT` ignorado por `third_party/`
- `data/reference_clip/madrid_R1.mov` ignorado por `*.mov`

Que estos archivos no aparezcan en GitHub es esperado y no indica perdida.

## Archivos versionados clave

Encontrados:

- `src/tracker/wasb_runner.py`
- `pyproject.toml`
- `uv.lock`
- `data/reference_clip/court_corners_pixel.json`
- `data/reference_clip/homography.json`
- `data/reference_clip/manual_annotation.example.json`
- `docs/decisions/`
- `docs/friction/FRICTION_LOG.md`
- `docs/stages/stage_0/`
- `docs/stages/stage_1/`

Faltantes versionados criticos: ninguno.

## Artefactos locales ignorados clave

Encontrados:

- `data/reference_clip/madrid_R1.mov` - `23,855,686` bytes
- `data/reference_clip/reference_frame.png` - `2,519,035` bytes
- `third_party/WASB-SBDT`
- `models/wasb/wasb_tennis_best.pth.tar` - `6,102,633` bytes
- `data/reference_clip/wasb_detections.csv` - `28,859` bytes
- `outputs/stage_2/wasb_detections_overlay.mp4` - `31,126,606` bytes

Faltantes locales criticos para validar Stage 2: ninguno.

## Documentacion Stage 2

Estado antes de esta auditoria:

- `docs/stages/stage_2/`: no existia
- `docs/stages/stage_2/visual_viability_review.md`: no existe
- `docs/stages/stage_2/local_recovery_audit.md`: no existe

Accion realizada:

- Se creo `docs/stages/stage_2/local_continuity_audit.md`.

## Copias huerfanas fuera del repo canonico

Revision solicitada:

```text
ls -la /home/msi/projects 2>/dev/null || true
du -sh /home/msi/projects/* 2>/dev/null || true
```

Resultado:

- `/home/msi/projects` existe pero esta vacio.
- No se detecto copia huerfana del proyecto.
- No se trabajo en `/home/msi/projects`.
- No se borro nada en esta sesion.

## Metadata del overlay MP4

Archivo:

```text
C:\Users\MSI\Desktop\TennisAI\outputs\stage_2\wasb_detections_overlay.mp4
/mnt/c/Users/MSI/Desktop/TennisAI/outputs/stage_2/wasb_detections_overlay.mp4
```

Metadata:

- Resolucion: `1920x1080`
- FPS: `60`
- Frames: `949`
- Duracion: `15.816667 s`
- OpenCV pudo abrir el archivo y leer el primer frame.

Conclusion: el MP4 overlay existe localmente y esta listo para validacion visual humana.

## Estadisticas del CSV de detecciones

Archivo:

```text
C:\Users\MSI\Desktop\TennisAI\data\reference_clip\wasb_detections.csv
/mnt/c/Users/MSI/Desktop/TennisAI/data/reference_clip/wasb_detections.csv
```

Estadisticas:

- Filas: `949`
- Confidence minima: `0.038088`
- Confidence maxima: `0.955775`
- Confidence media: `0.7465421485774499`
- Confidence mediana: `0.859709`
- Frames con `confidence >= 0.5`: `804`
- Detection rate aparente: `0.8472075869336143`

Nota: estas estadisticas no sustituyen la validacion visual. Solo indican que WASB produjo detecciones con confianza; el usuario debe confirmar si los circulos caen sobre la pelota real.

## Conclusion operativa

Resultado: **A) podemos continuar con validacion visual porque MP4/CSV existen.**

Tambien es cierto que **B) Stage 2 puede regenerarse localmente** si hiciera falta, porque existen:

- `data/reference_clip/madrid_R1.mov`
- `models/wasb/wasb_tennis_best.pth.tar`
- `third_party/WASB-SBDT`
- `src/tracker/wasb_runner.py`

No falta ningun insumo critico local para continuar Stage 2.

Siguiente paso humano:

1. Abrir `C:\Users\MSI\Desktop\TennisAI\outputs\stage_2\wasb_detections_overlay.mp4`.
2. Emitir veredicto visual:
   - `A`: WASB detecta suficientemente bien; cerrar gate visual de Stage 2 y planificar cierre formal.
   - `B`: WASB no detecta bien; diagnosticar Stage 2 sin cambiar de modelo todavia.
   - `C`: resultado dudoso; revisar thresholds/frames del overlay antes de decidir.

No se avanzo a Stage 3.
