# Tennis Vision AI v2

Sistema para analizar clips reales de tenis con camara fija de broadcast y generar, por etapas, dos vistas 2D del rally:

- Vista superior: trayectoria de la pelota proyectada sobre la cancha.
- Vista lateral: trayectoria con altura inferida fisicamente entre botes.

Este repositorio vive directamente en la raiz de trabajo del proyecto. No debe anidarse dentro de otra carpeta de proyecto.

## Estado actual

- Stage actual: `Stage 0 - Fundacion`
- Entorno objetivo: WSL2 + Ubuntu 24.04
- Python objetivo: 3.11
- Gestor de entorno: `uv`
- Vision computacional: todavia no se ejecuta en Stage 0

## Estructura

```text
README.md
ROADMAP.md
pyproject.toml
uv.lock
data/               # local, no versionado salvo README/templates
models/             # local, no versionado salvo README
outputs/            # local, no versionado salvo README
src/                # codigo fuente
scripts/            # utilitarios
docs/               # documentacion viva
legacy/             # referencia negativa del proyecto anterior
```

## Setup desde cero

1. Clonar o abrir el repositorio.
2. Entrar a la raiz del proyecto.
3. Verificar WSL2 Ubuntu 24.04:

```bash
uname -a
cat /etc/os-release
echo "$USER"
```

4. Instalar dependencias base del sistema si faltan:

```bash
sudo apt update
sudo apt install -y build-essential git ffmpeg curl
```

5. Instalar `uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

6. Crear el entorno Python:

```bash
uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev]"
uv lock
```

7. Verificar el entorno:

```bash
python scripts/verify_env.py
```

## Datos locales requeridos

Stage 0 requiere que el usuario prepare manualmente:

- `data/reference_clip/madrid_R1.mp4`
- `data/reference_clip/reference_frame.png`
- `data/reference_clip/manual_annotation.json`

Estos archivos no se commitean. Usar `data/reference_clip/manual_annotation.example.json` como punto de partida para la anotacion.

## Por donde seguir

- Roadmap general: [ROADMAP.md](ROADMAP.md)
- Stage 0: [docs/stages/stage_0/STAGE_0.md](docs/stages/stage_0/STAGE_0.md)
- Validacion por etapa: [docs/validation/VALIDATION_FRAMEWORK.md](docs/validation/VALIDATION_FRAMEWORK.md)
- Decisiones tecnicas: [docs/decisions/](docs/decisions/)
- Friccion: [docs/friction/FRICTION_LOG.md](docs/friction/FRICTION_LOG.md)
