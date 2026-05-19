# Friction Log

Tabla append-only. No reescribir entradas antiguas; agregar resolucion o nueva entrada si cambia el diagnostico.

| ID | Fecha | Stage | Categoria | Descripcion | Costo (h) | Resolucion | Status |
|----|-------|-------|-----------|-------------|-----------|------------|--------|
| F-0001 | 2026-05-18 | 0 | ENV | `wsl.exe` dentro del sandbox no ve distros, aunque el usuario Windows `MSI` si tiene Ubuntu 24.04 en WSL2. | 0.5 | Resuelto operativamente: ejecutar comandos WSL fuera del sandbox/con permiso explicito para acceder a las distros del usuario. | Resuelto |
| F-0002 | 2026-05-18 | 0 | DEP | `uv pip install -e .[dev]` quedo colgado en ruta montada `/mnt/c`; al detenerlo, NumPy quedo parcialmente escrito. | 0.5 | Reinstalado con `UV_LINK_MODE=copy` desde `pyproject.toml`; NumPy volvio a 1.26.4 y `verify_env.py` sale 0. | Resuelto |
| F-0003 | 2026-05-18 | 0 | DOC | Cierre formal pendiente de Stage 0: ADR-0001 a ADR-0005 quedaron en estado `Propuesta` aunque el usuario autorizo su aceptacion verbal durante la planificacion. | 0.1 | Aplicado en Stage 1 via auto-aceptacion autorizada por usuario, con commit dedicado. | Resuelto |
| F-0004 | 2026-05-18 | 0 | DOC | Cierre formal pendiente de Stage 0: assets del clip de referencia en disco aun no verificados en el carry-over. | 0.0 | Verificado en 1.0: existe `madrid_R1.mov`; faltan `reference_frame.png` y `manual_annotation.json`. Stage 1 puede continuar con extraccion del frame si el usuario aprueba 1.1; anotacion narrativa no bloquea Stage 1. | Resuelto |
| F-0005 | 2026-05-18 | 1 | DEP | `ffmpeg` no esta instalado en WSL al iniciar 1.1, aunque Stage 1 sugeria usarlo para extraer `reference_frame.png`. | 0.1 | Resuelto de raiz: `ffmpeg` 6.1.1 instalado en WSL Ubuntu 24.04 y verificado el 2026-05-19. | Resuelto |
| F-0006 | 2026-05-18 | 1 | ENV | WSLg/OpenCV GUI no pudo abrir `cv2.imshow`: Qt encontro plugin `xcb` pero no pudo inicializar plataforma grafica. | 0.2 | Resuelto operativamente con fallback; pendiente solucion estructural para Stages 5/6. | Resuelto |
| F-0007 | 2026-05-19 | 2 | DEP | Instalacion de dependencias tracker/WASB en `/mnt/c` tomo ~18.7 min y genero `.venv` de 5.2G, superando el umbral de 15 min definido para revisar ADR-0007. | 0.3 | Diagnostico: no aceptar ADR-0007 aun; recomendar migracion del repo a filesystem nativo de WSL antes de descargar pesos/correr inferencia. | Abierto |
