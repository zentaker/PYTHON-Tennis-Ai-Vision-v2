# ADR-0003: uv como gestor de entorno

- **Status:** Propuesta
- **Fecha:** 2026-05-18
- **Stage:** 0

## Contexto

El proyecto necesita un entorno reproducible, rapido de reinstalar y con lock file determinista. Tambien necesita gestionar Python 3.11 dentro de Ubuntu 24.04 sin depender de PPAs ni modificar el Python del sistema.

## Decision

Usar `uv` como gestor de entorno, dependencias, lock file y version de Python.

## Alternativas consideradas

- `venv` + `pip` - simple, pero sin lock file robusto y sin gestion de versiones de Python.
- `conda` - valido, pero mas pesado y con resolucion mas lenta.
- PPA `deadsnakes` - introduce dependencia del sistema y mas friccion operacional.

## Consecuencias

- Positivas: setup rapido, lock reproducible y Python 3.11 gestionado por proyecto.
- Negativas / riesgos: requiere instalar `uv` y que el entorno tenga acceso de red inicial.

## Notas

`uv.lock` debe generarse dentro del entorno objetivo antes de cerrar Stage 0.
