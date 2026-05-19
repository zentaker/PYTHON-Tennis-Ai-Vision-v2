# Friction Log

Tabla append-only. No reescribir entradas antiguas; agregar resolucion o nueva entrada si cambia el diagnostico.

| ID | Fecha | Stage | Categoria | Descripcion | Costo (h) | Resolucion | Status |
|----|-------|-------|-----------|-------------|-----------|------------|--------|
| F-0001 | 2026-05-18 | 0 | ENV | `wsl.exe` dentro del sandbox no ve distros, aunque el usuario Windows `MSI` si tiene Ubuntu 24.04 en WSL2. | 0.5 | Resuelto operativamente: ejecutar comandos WSL fuera del sandbox/con permiso explicito para acceder a las distros del usuario. | Resuelto |
| F-0002 | 2026-05-18 | 0 | DEP | `uv pip install -e .[dev]` quedo colgado en ruta montada `/mnt/c`; al detenerlo, NumPy quedo parcialmente escrito. | 0.5 | Reinstalado con `UV_LINK_MODE=copy` desde `pyproject.toml`; NumPy volvio a 1.26.4 y `verify_env.py` sale 0. | Resuelto |
| F-0003 | 2026-05-18 | 0 | DOC | Cierre formal pendiente de Stage 0: ADR-0001 a ADR-0005 quedaron en estado `Propuesta` aunque el usuario autorizo su aceptacion verbal durante la planificacion. | 0.1 | Aplicado en Stage 1 via auto-aceptacion autorizada por usuario, con commit dedicado. | Resuelto |
| F-0004 | 2026-05-18 | 0 | DOC | Cierre formal pendiente de Stage 0: assets del clip de referencia en disco aun no verificados en el carry-over. | 0.0 | Pendiente de pre-condicion 1.0: verificar `data/reference_clip/` antes de iniciar calibracion. | Abierto |
