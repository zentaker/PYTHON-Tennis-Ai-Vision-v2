# Friction Log

Tabla append-only. No reescribir entradas antiguas; agregar resolucion o nueva entrada si cambia el diagnostico.

| ID | Fecha | Stage | Categoria | Descripcion | Costo (h) | Resolucion | Status |
|----|-------|-------|-----------|-------------|-----------|------------|--------|
| F-0001 | 2026-05-18 | 0 | ENV | `wsl.exe` dentro del sandbox no ve distros, aunque el usuario Windows `MSI` si tiene Ubuntu 24.04 en WSL2. | 0.5 | Resuelto operativamente: ejecutar comandos WSL fuera del sandbox/con permiso explicito para acceder a las distros del usuario. | Resuelto |
| F-0002 | 2026-05-18 | 0 | DEP | `uv pip install -e .[dev]` quedo colgado en ruta montada `/mnt/c`; al detenerlo, NumPy quedo parcialmente escrito. | 0.5 | Reinstalado con `UV_LINK_MODE=copy` desde `pyproject.toml`; NumPy volvio a 1.26.4 y `verify_env.py` sale 0. | Resuelto |
