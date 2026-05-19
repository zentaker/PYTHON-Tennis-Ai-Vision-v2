# Friction Log

Tabla append-only. No reescribir entradas antiguas; agregar resolucion o nueva entrada si cambia el diagnostico.

| ID | Fecha | Stage | Categoria | Descripcion | Costo (h) | Resolucion | Status |
|----|-------|-------|-----------|-------------|-----------|------------|--------|
| F-0001 | 2026-05-18 | 0 | ENV | `wsl.exe` visible desde el agente reporta que no hay distribuciones instaladas, aunque el Stage 0 asumia Ubuntu 24.04 operativo. | 0.25 | Pendiente: usuario debe verificar `wsl.exe --list --verbose` fuera del entorno del agente o habilitar la distro para Codex. | Abierto |
