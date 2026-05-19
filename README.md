# Tennis Vision AI v2

Proyecto para análisis de video de broadcast de tenis con generación progresiva de:

- Vista superior 2D de la trayectoria de la pelota sobre la cancha.
- Vista lateral 2D con altura inferida físicamente entre botes.

## Estado actual

Stage 1 cerrado. Stage 2 en preparación.

- Stage 0: fundación, entorno y documentación base.
- Stage 1: calibración de cancha cerrada con gate visual firmado.
- Stage 2: detección de pelota, pendiente de prompt y revisión previa.

Roadmap completo: [ROADMAP.md](ROADMAP.md)

## Setup

Entorno objetivo:

- WSL2 Ubuntu 24.04
- Python 3.11
- `uv`

Desde la raíz del repo en WSL:

```bash
cd /mnt/c/Users/MSI/Desktop/TennisAI
```

Instalar `uv` si no existe:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Crear entorno e instalar dependencias:

```bash
uv venv --python 3.11
source .venv/bin/activate
UV_LINK_MODE=copy uv pip install -e ".[dev]"
uv lock
```

Verificar entorno:

```bash
python scripts/verify_env.py
```

Nota: si se trabaja desde Codex, los comandos `wsl.exe` deben ejecutarse fuera del sandbox cuando necesiten ver las distros WSL del usuario Windows.

## Estructura del proyecto

```text
docs/                 Documentación viva, stages, ADRs, validación y fricción
src/                  Código fuente del pipeline
scripts/              Utilitarios operativos
data/                 Datos locales no versionados
models/               Pesos/modelos locales no versionados
outputs/              Salidas generadas no versionadas
legacy/               Postmortem del proyecto anterior
```

Entradas principales:

- [docs/README.md](docs/README.md)
- [docs/stages/stage_1/exit_report.md](docs/stages/stage_1/exit_report.md)
- [docs/decisions/](docs/decisions/)
- [docs/friction/FRICTION_LOG.md](docs/friction/FRICTION_LOG.md)

## Datos requeridos para reproducir

El video de referencia no está incluido en el repositorio por motivos de derechos.

Para reproducir Stage 1 o preparar Stage 2, un colaborador debe conseguir por separado el clip Nivel A y colocarlo en:

```text
data/reference_clip/madrid_R1.mov
```

Los JSON de calibración de Stage 1 sí están en el repo y se cargan automáticamente:

```text
data/reference_clip/court_corners_pixel.json
data/reference_clip/homography.json
```

El frame de referencia y los renders son derivados del video y se regeneran localmente:

```text
data/reference_clip/reference_frame.png
outputs/stage_1/
```

Los pesos de modelos se descargarán automáticamente en Stage 2 al primer uso, pendiente de implementación.

## Test de reproducibilidad

Primer paso de validación tras clonar y preparar el entorno:

```bash
python scripts/verify_env.py
```

Después de colocar `data/reference_clip/madrid_R1.mov`, Stage 1 puede regenerar `reference_frame.png`, reportes y renders usando los JSON de calibración versionados.

## Aviso legal

Este repositorio contiene scripts y documentación para análisis de video de broadcast deportivo. El video de referencia (Madrid Open, TennisTV/ATP) no se incluye en el repo por motivos de derechos. Los frames derivados que aparecen en `outputs/` se usan únicamente con fines de investigación técnica personal.

## Reglas de repositorio

- No commitear videos, pesos de modelos, datasets, salidas generadas ni secretos.
- `data/`, `models/`, `outputs/` son carpetas locales.
- Cualquier decisión técnica relevante se documenta como ADR.
- Stage 2 no debe comenzar hasta validar ADR-0007 y ADR-0009.
