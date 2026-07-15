# Entorno de desarrollo nativo macOS

**Auditoría:** 2026-07-14

## Sistema encontrado

| Componente | Estado | Detalle |
| --- | --- | --- |
| Arquitectura | Found | Intel `x86_64` |
| macOS | Found | `15.7.7`, build `24G720` |
| Shell | Found | `/bin/zsh` |
| uv | Found | `0.11.28`, `/Users/sandra/.local/bin/uv` |
| Python gestionado por uv | Found | CPython `3.11.15` x86_64 |
| Python del sistema | Found | `/usr/bin/python3`, versión `3.9.6`; no usar para el proyecto |
| Git | Found | `2.55.0`, `/usr/local/bin/git` |
| Homebrew | Found | `6.0.10`, `/usr/local/bin/brew` |
| Command Line Tools | Found | `/Library/Developer/CommandLineTools` |
| ffmpeg / ffprobe | Found | `8.1.2`, `/usr/local/bin/ffmpeg` y `/usr/local/bin/ffprobe` |
| WSL | No disponible | WSL es una función de Windows, no de macOS |
| CUDA/NVIDIA | No aplicable | Stage 2 se ejecuta en una máquina GPU externa |

No se instalaron Ubuntu, WSL, Docker ni UTM. Docker/UTM podrían servir en el futuro para
compatibilidad Linux sobre CPU, pero no proporcionan CUDA/NVIDIA en este Mac Intel y no
son necesarios para el flujo actual.

## Python y `.venv`

La `.venv` existente usa:

```text
/Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2/.venv/bin/python
Python 3.11.15
macOS-15.7.7-x86_64-i386-64bit
```

La auditoría encontró paquetes base utilizables pero entrypoints dev ausentes: `pytest` y
`ruff` no podían iniciarse. No se borró ni recreó la `.venv`; se reparó de forma
incremental:

```bash
uv sync --frozen --extra dev
```

El comando restauró 32 componentes dev. El entorno final contiene 46 paquetes
compatibles según `uv pip check`. No se instaló el extra `tracker`, PyTorch ni CUDA.
`uv.lock` mantuvo su SHA-256
`cccc36d9739887d16ed46b107027966aad755393053ddf2d82d89ec212367b7c`.

Setup recomendado para otro checkout macOS:

```bash
cd /Users/sandra/Desktop/PYTHON-Tennis-Ai-Vision-v2
uv python install 3.11  # solo si `uv python list` no muestra 3.11
uv sync --frozen --extra dev
uv run pytest
uv run ruff check .
```

`uv` y Python 3.11 ya existían en esta máquina; no fueron reinstalados. FFmpeg fue
instalado mediante Homebrew antes de esta verificación y quedó correctamente enlazado
desde `/usr/local/opt/ffmpeg`; no se reinstaló ni se ejecutó `brew link`. El preflight A2
usa ahora FFprobe para obtener PTS reales y FFmpeg queda disponible para utilidades
multimedia ligeras.

## Validación local

Resultado de la auditoría:

- `98 passed` con Python 3.11.15;
- Ruff limpio;
- `compileall` correcto para `src`, `scripts` y `tests`;
- `scripts/replit_smoke_test.py`: correcto;
- `git diff --check`: correcto;
- cinco activos A2 presentes;
- MP4 con SHA esperado y 527 frames;
- preflight Stage 2: `PASS_WITH_WARNINGS`, 527 frames completos y sin inferencia.

## Qué se ejecuta en Mac

macOS es el entorno principal para:

- código, tests, lint y documentación;
- Stage 1: extracción/revisión de frames, calibración, homografía y renders;
- lógica ligera de Stage 3: lectura de CSV, smoothing y validaciones, cuando existan
  detecciones reales;
- Stage 4: anotación y normalización de eventos;
- preflight de Stage 2 sin modelo.

Stage 2/WASB requiere Linux o WSL con GPU NVIDIA/CUDA, checkpoint y WASB-SBDT. No debe
ejecutarse en este Mac. Stage 3 A2 no empieza hasta que Stage 2 devuelva detecciones
reales y pase su gate visual. Stage 5 continúa sin iniciar.

## Flujo Mac ↔ máquina GPU

1. En Mac: desarrollar, ejecutar tests y publicar únicamente código/JSON/documentación
   pequeños mediante Git.
2. Enviar por un canal de archivos, no por Git, el MP4, checkpoint y WASB-SBDT.
3. En Linux/WSL/GPU: instalar el extra tracker, ejecutar preflight runtime y luego WASB.
4. Devolver CSV, overlay y reporte de inferencia.
5. En Mac: validar 527 filas, timestamps, bounds y overlay; emitir gate A/B/C.

El inventario exacto está en
`docs/levels/level_a2/STAGE_2_EXTERNAL_HANDOFF.md`.
