# Tennis Vision AI v2

Proyecto para analizar video de broadcast de tenis y generar progresivamente:

- una vista superior 2D de la trayectoria de la pelota sobre la cancha;
- una vista lateral 2D con altura inferida fisicamente entre botes.

## Estado actual

Stage 3 esta cerrada y validada. Stage 4 Nivel A2 esta cerrada con gate humano A y usa
eventos anotados manualmente; no intenta detectar golpes o botes automaticamente.
Stage 5A/5A.1 están cerradas. Los baselines Stage 5B v1 y v2 fueron rechazados por el
gate humano; la preparación de la arquitectura Player-Aware P1 está completa, sin
ejecutar todavía inferencia pesada.

La pasada historica Madrid R1 se conserva como Nivel A. La pasada activa Nivel A2 tiene
Stage 1–4 cerradas y continúa con Stage 5A. Ver
[docs/levels/level_a2/README.md](docs/levels/level_a2/README.md).

| Stage | Estado |
| --- | --- |
| 0 - Fundacion | Cerrada funcionalmente; cierre documental reconciliado |
| 1 - Calibracion | Cerrada con gate visual firmado |
| 2 - Deteccion WASB | Cerrada con limitaciones conocidas |
| 3 - Suavizado temporal | Cerrada y validada visualmente (`v1.3.0`) |
| 4 - Eventos Nivel A | `CLOSED_SUCCESSFULLY` (A2, gate A) |
| 5A - Calibracion/observabilidad 3D | `CLOSED_WITH_REFINED_VERTICAL_CALIBRATION` |
| 5A.1 - Referencia vertical de red | Cerrada exitosamente |
| 5B - Reconstruccion X,Y,Z | `V1_V2_REJECTED_BY_HUMAN_GATE` |
| 5C - Vista superior derivada | No iniciada |
| 6 - Vista lateral derivada | No iniciada |
| 7 - Validacion final | No iniciada |

La base reusable de Player-Aware P1 está en la rama `agent/player-perception-p1`.
Su ejecución real requiere pasar primero el [GPU provider acceptance gate](docs/ops/GPU_PROVIDER_ACCEPTANCE_GATE.md).

Roadmap completo: [ROADMAP.md](ROADMAP.md).

## Core Stage 2A — Session Platform

The local Session Platform foundation is implemented as a review candidate. It
provides a FastAPI Session API V1, PostgreSQL/Alembic metadata, MinIO/S3 object
storage, presigned browser uploads, and a deterministic OpenAPI contract without
loading the tracking or inference stack. Browser uploads use a public MinIO
endpoint while API storage operations use an internal endpoint. See
[docs/platform/STAGE2A_SESSION_PLATFORM.md](docs/platform/STAGE2A_SESSION_PLATFORM.md)
and [docs/platform/LOCAL_DEVELOPMENT.md](docs/platform/LOCAL_DEVELOPMENT.md).

Install the optional platform dependencies with `uv sync --extra platform`.
The generated Postman client and local environment live in
[docs/postman](docs/postman/README.md); OpenAPI remains their single source of
truth.

## Setup ligero en macOS

El desarrollo de Stage 4, la documentacion y los tests no requieren tracker, PyTorch ni
WASB. Se necesita Python 3.11 y `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uv python install 3.11
uv sync --extra dev --locked --python 3.11
uv run pytest
```

No ejecutar `uv sync --extra tracker` en macOS Intel. El lock actual incluye una version
de PyTorch sin distribucion para esa plataforma y Stage 4 no la necesita.

## Entorno pesado WSL/Linux

WSL2 Ubuntu 24.04 x86_64 sigue siendo el entorno canonico para WASB, checkpoints e
inferencia pesada. Con los artefactos locales restaurados:

```bash
uv python install 3.11
uv sync --extra dev --extra tracker --locked --python 3.11
uv run python scripts/verify_env.py
```

`scripts/verify_env.py` conserva el gate historico de WSL2/Linux y por eso no termina en
verde en macOS aunque el entorno ligero sea correcto.

## Estructura del proyecto

```text
docs/                 Documentacion viva, stages, ADRs, validacion y friccion
src/                  Codigo fuente del pipeline
scripts/              Utilitarios operativos y smoke tests
tools/                Herramientas estaticas que no requieren Python
data/                 Datos locales y metadata versionada
models/               Pesos/modelos locales no versionados
outputs/              Salidas generadas no versionadas
third_party/          Codigo externo local no versionado
legacy/               Postmortem del proyecto anterior
```

Entradas principales:

- [docs/README.md](docs/README.md)
- [docs/stages/stage_3/exit_report.md](docs/stages/stage_3/exit_report.md)
- [docs/stages/stage_4/STAGE_4.md](docs/stages/stage_4/STAGE_4.md)
- [docs/validation/VALIDATION_FRAMEWORK.md](docs/validation/VALIDATION_FRAMEWORK.md)
- [docs/decisions/](docs/decisions/)

## Artefactos locales

Git contiene codigo, tests, documentacion y la calibracion JSON. Por motivos de derechos,
tamanio y reproducibilidad entre plataformas, no contiene:

- `data/reference_clip/madrid_R1.mov`;
- `data/reference_clip/reference_frame.png`;
- CSV de detecciones;
- outputs de Stage 1-4;
- checkpoints, modelos ni `third_party/WASB-SBDT`.

Para continuar Stage 4 Nivel A se necesitan localmente:

```text
outputs/stage_3/smoothed_trajectory.csv
data/reference_clip/manual_annotation.json
data/reference_clip/homography.json
```

El ultimo archivo ya esta versionado. El video y el overlay suavizado son auxiliares para
la anotacion y el gate humano.

## Replit

La migracion a Replit se completo y queda archivada como evidencia operativa historica.
No es un blocker ni un proximo paso activo:

- [docs/ops/REPLIT_MIGRATION.md](docs/ops/REPLIT_MIGRATION.md)
- [docs/ops/REPLIT_SMOKE_TEST_REPORT.md](docs/ops/REPLIT_SMOKE_TEST_REPORT.md)

## Reglas del repositorio

- No commitear videos, outputs, modelos, checkpoints, datasets, `third_party` ni secretos.
- No inventar eventos o datos para hacer pasar un gate.
- Cualquier decision tecnica relevante se documenta como ADR.
- Cada stage conserva su artefacto, evidencia y gate humano.

## Aviso legal

El video de referencia de Madrid Open/TennisTV/ATP no se distribuye con el repositorio.
Los frames y renders locales se usan exclusivamente para investigacion tecnica personal.
