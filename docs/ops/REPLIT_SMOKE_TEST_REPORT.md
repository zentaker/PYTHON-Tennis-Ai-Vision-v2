# Replit Smoke Test Report

> **Estado: completada y archivada.** La migracion Replit dejo de ser un blocker y no
> forma parte de los proximos pasos activos. Los resultados, rutas y fallos descritos
> abajo corresponden a la ejecucion original y se preservan como evidencia historica.
> Actualmente macOS se usa para desarrollo ligero y WSL/Linux para WASB.

Date/time: 2026-05-23 02:13:23 -05:00

## Scope

This report verifies whether the current Tennis Vision AI v2 checkout can be used as a lightweight auxiliary Replit-style development environment.

Replit is intended for:

- code and documentation edits;
- lightweight tests;
- agent workflow;
- web tooling such as `manual_event_annotator`;
- Stage documentation.

Replit is not intended to replace the local heavy environment. Do not use it initially for WASB, `torch`, videos, checkpoints, model files, generated outputs, CUDA, or large `third_party` payloads.

## Repository

Local path:

```text
C:\Users\Are\Desktop\tennisAI
```

GitHub remote:

```text
https://github.com/zentaker/PYTHON-Tennis-Ai-Vision-v2.git
```

Branch:

```text
main
```

Local HEAD:

```text
39c9a324070d42e235571d8b9c98cc66290a4c84
39c9a32 ops(replit): prepare local setup and migration notes
```

Remote `origin/main` observed by `git ls-remote`:

```text
436a149b0d5af5447cafdf843ac0a4d405565035
```

Git status:

```text
## main...origin/main [ahead 1]
```

Conclusion: the local ops commit `39c9a32` is not yet synchronized with GitHub. A Replit import from GitHub will not see the latest ops files until `git push origin main` is run from the local repo.

No push was performed during this verification.

## Structure Check

Required paths:

```text
.git                  OK
src/                  OK
docs/                 OK
scripts/              OK
data/reference_clip/  OK
tests/                OK
```

The repository root is correctly located at `C:\Users\Are\Desktop\tennisAI`.

## Python And Lightweight Environment

Detected Python:

```text
Python 3.11.6
C:\Program Files\Inkscape\bin\python.exe
```

Detected tooling:

```text
uv: not installed
py: not available on PATH
pip: not installed in the active Python
ensurepip: reports bundled pip 23.2.1
```

Attempted virtual environment creation:

```text
python -m venv .venv
```

Result:

```text
Error: Command '['C:\\Users\\Are\\Desktop\\tennisAI\\.venv\\bin\\python.exe', '-m', 'ensurepip', '--upgrade', '--default-pip']' returned non-zero exit status 103.
```

The failed partial `.venv` was removed. No global package installation was performed.

Conclusion: this current Windows checkout cannot create the requested lightweight venv with the available Python. A real Replit setup should use Python 3.11 with either:

```bash
uv sync
```

or:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Do not install the `tracker` extra for the first Replit pass.

## Import Check

Command:

```text
python -c "import importlib; ..."
```

Results:

```text
OK src
OK src.court.coordinates
OK src.tracker.trajectory_io
FAIL src.events.event_schema: ModuleNotFoundError: No module named 'src.events'
```

No OpenCV, WASB, video, checkpoint, or model import was required for the successful imports.

## Smoke Test

Command:

```text
python scripts/replit_smoke_test.py
```

Result:

```text
OK import src
OK import src.court.coordinates
OK import src.tracker.trajectory_io
FAIL event_loader import
  src.events.event_loader: No module named 'src.events'
  src.event_loader: No module named 'src.event_loader'
  event_loader: No module named 'event_loader'
```

Conclusion: the smoke test executes without invoking `cv2`, WASB, videos, checkpoints, or model files, but it does not pass because the event package/loader is absent in this checkout.

## Manual Event Annotator Availability

Search result:

```text
manual_event_annotator: not found
event_schema: not found
event_loader: not found
src/events/: not found
```

Conclusion: the manual event annotator is not available in the current local checkout. If it already exists elsewhere, it has not been committed or synchronized into this repository state.

## Missing Dependencies Or Assets

Missing or unavailable in this verification environment:

- working project `.venv`;
- active `pip`;
- `uv`;
- `pytest`;
- `src.events.event_schema`;
- event loader module;
- `manual_event_annotator`.

Intentionally not installed or used:

- WASB;
- `torch`;
- tracker extras;
- model checkpoints;
- videos;
- generated outputs;
- `third_party` payloads.

## Replit Readiness

Status: partially ready, with blockers.

Ready now:

- repository structure is correct;
- lightweight source imports that already exist are usable;
- ops documentation exists locally;
- the smoke test is lightweight and avoids heavy dependencies.

Blocked before a clean Replit auxiliary workflow:

- push local commit `39c9a32` to GitHub;
- create the Replit Python 3.11 environment;
- install base/dev dependencies only;
- add or synchronize `src.events.event_schema`;
- add or synchronize the event loader expected by `scripts/replit_smoke_test.py`;
- add or synchronize `manual_event_annotator`.

After those blockers are resolved, Replit can be used for Stage 4 event work with the user's manual narrative or the manual annotation tool. It should still not be used for Stage 5, WASB, heavy video processing, checkpoints, outputs, or `third_party`.
