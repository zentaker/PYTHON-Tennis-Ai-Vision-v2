# Replit Migration Notes

> **Estado: completada y archivada.** Replit ya no es un blocker ni un proximo paso
> activo. El contenido siguiente se conserva como evidencia historica de la migracion.
> El entorno activo es macOS para desarrollo ligero; WSL/Linux sigue siendo necesario
> para WASB e inferencia pesada.

## Purpose

Replit is an auxiliary environment for Tennis Vision AI v2. It is not a replacement for the local heavy environment used for video processing, WASB, checkpoints, outputs, or large third-party code.

Use Replit for:

- code review and small edits;
- docs and ops notes;
- lightweight Python tests;
- HTML/JS tools;
- agent workflow and GitHub synchronization.

Do not use Replit initially for:

- WASB inference;
- video processing;
- checkpoint or model installation;
- generated outputs;
- large `third_party` payloads;
- CUDA/GPU assumptions;
- long-running processing jobs.

## Import From GitHub

1. Push the local ops commit to GitHub from the local machine.
2. In Replit, choose import from GitHub.
3. Use:

```text
https://github.com/zentaker/PYTHON-Tennis-Ai-Vision-v2.git
```

4. Select the intended branch, currently:

```text
main
```

5. Configure Python 3.11 if Replit asks for a runtime version.

## Lightweight Setup

Preferred when `uv` is available:

```bash
uv sync
```

Fallback:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Do not install the `tracker` extra during the initial Replit setup:

```bash
# Do not run this for the first Replit migration pass:
python -m pip install -e ".[tracker]"
```

## Smoke Test

Run:

```bash
python scripts/replit_smoke_test.py
```

The smoke test is intentionally light. It should only import modules that do not require OpenCV, WASB, videos, checkpoints, or model files.

Current known gap: the repo snapshot does not include an `event_loader` module. The smoke test will report that until the lightweight event loader is added or restored in the appropriate project stage.

## Folders And Files To Keep Out Of Replit

Do not upload or generate these payloads in the first Replit pass:

- `outputs/`
- `models/`
- `third_party/`
- `.venv/`
- local video files such as `*.mp4`, `*.mov`, `*.avi`, `*.mkv`, `*.webm`
- model weights such as `*.pt`, `*.pth`, `*.ckpt`, `*.onnx`, `*.safetensors`
- binary reference clips under `data/reference_clip/`

The repo keeps small reference metadata files in Git, but not the heavy binary assets.

## GitHub Sync Workflow

Local to Replit:

```bash
git status -sb
git add <files>
git commit -m "<message>"
git push origin main
```

Replit to local:

```bash
git status -sb
git pull --ff-only origin main
```

Before moving changes between environments, check:

```bash
git status -sb
git log --oneline -5
```

Avoid force pushes. If branches diverge, inspect the history before resolving.

## Readiness Criteria

Replit is ready as an auxiliary environment when:

- the repo imports directly from GitHub;
- Python 3.11 is active;
- base and dev dependencies install without tracker/WASB extras;
- `python scripts/replit_smoke_test.py` prints OK;
- lightweight tests pass;
- no videos, outputs, checkpoints, models, or `third_party` payloads are present.
