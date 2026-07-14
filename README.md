# Tennis Vision AI v2

Proyecto para analizar video de broadcast de tenis y generar progresivamente:

- una vista superior 2D de la trayectoria de la pelota sobre la cancha;
- una vista lateral 2D con altura inferida fisicamente entre botes.

## Estado actual

Stage 3 esta cerrada y validada. Stage 4 Nivel A esta en implementacion y usa eventos
anotados manualmente; no intenta detectar golpes o botes automaticamente.

La pasada historica Madrid R1 se conserva como Nivel A. La pasada activa Nivel A2 vuelve
a Stage 1 con un clip MP4 nuevo; esta preparada y pendiente de aprobacion humana del frame
de referencia. Ver [docs/levels/level_a2/README.md](docs/levels/level_a2/README.md).

| Stage | Estado |
| --- | --- |
| 0 - Fundacion | Cerrada funcionalmente; cierre documental reconciliado |
| 1 - Calibracion | Cerrada con gate visual firmado |
| 2 - Deteccion WASB | Cerrada con limitaciones conocidas |
| 3 - Suavizado temporal | Cerrada y validada visualmente (`v1.3.0`) |
| 4 - Eventos Nivel A | En progreso |
| 5 - Vista superior | No iniciada |
| 6 - Vista lateral | No iniciada |
| 7 - Validacion final | No iniciada |

Roadmap completo: [ROADMAP.md](ROADMAP.md).

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
