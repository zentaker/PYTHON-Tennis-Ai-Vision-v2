# Env Report - Stage 0

**Fecha:** 2026-05-18  
**Workspace raiz:** `C:\Users\MSI\Desktop\TennisAI`  
**Estado:** WSL verificado; nota operativa sobre sandbox

## Comandos solicitados por Stage 0

```bash
uname -a
cat /etc/os-release
echo "$USER"
```

## Evidencia obtenida desde el agente

### Nota operativa

Los comandos `wsl.exe` ejecutados dentro del sandbox aislado no ven las distribuciones registradas en el usuario Windows `MSI`. Al ejecutar `wsl.exe` fuera del sandbox, con permiso explicito del usuario, WSL queda disponible correctamente. Esta es la via operativa para este proyecto.

### `wsl.exe --list --verbose`

Exit code: 0

```text
NAME            STATE    VERSION
* Ubuntu        Running  2
  Ubuntu-22.04  Stopped  2
```

### `wsl.exe uname -a`

Exit code: 0

```text
Linux DESKTOP-61O065D 6.6.87.2-microsoft-standard-WSL2 #1 SMP PREEMPT_DYNAMIC Thu Jun 5 18:30:46 UTC 2025 x86_64 x86_64 x86_64 GNU/Linux
```

### `wsl.exe cat /etc/os-release`

Exit code: 0

```text
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
```

### `wsl.exe bash -lc 'echo $USER'`

Exit code: 0

```text
msi
```

## Entorno Python

```text
Python: 3.11.15
NumPy: 1.26.4
OpenCV: 4.11.0
SciPy: 1.17.1
uv.lock: generado
```

## `scripts/verify_env.py`

Ejecutado dentro de WSL desde `/mnt/c/Users/MSI/Desktop/TennisAI` con exit code 0.

```text
[OK] Python 3.11.15
[OK] Ubuntu 24.04 detectado
[OK] NumPy 1.26.4
[OK] OpenCV 4.11.0
[OK] SciPy 1.17.1
[OK] Ruta existe: data
[OK] Ruta existe: data/reference_clip
[OK] Ruta existe: models
[OK] Ruta existe: models/wasb
[OK] Ruta existe: outputs
[WARN] Clip local no encontrado: data/reference_clip/madrid_R1.mp4
[WARN] Frame de referencia no encontrado: data/reference_clip/reference_frame.png
[WARN] Anotacion local no encontrada: data/reference_clip/manual_annotation.json

Verificacion completada sin fallas criticas.
```

## Pendientes de entorno sistema

`ffmpeg` y `gcc/build-essential` no estaban disponibles al momento de la verificacion. No bloquean `scripts/verify_env.py`, pero deben instalarse con `sudo apt install -y build-essential ffmpeg` antes de etapas que procesen video o compilen dependencias nativas.
