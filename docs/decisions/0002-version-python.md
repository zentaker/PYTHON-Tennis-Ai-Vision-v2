# ADR-0002: Python 3.11 como version objetivo

- **Status:** Aceptada
- **Fecha:** 2026-05-18
- **Stage:** 0

## Contexto

Ubuntu 24.04 trae Python 3.12 por defecto, pero varias librerias de vision computacional y repositorios de modelos publicados suelen estabilizar primero en Python 3.10 o 3.11. El proyecto necesita reducir friccion de compatibilidad para WASB, OpenCV, NumPy, SciPy y herramientas de desarrollo.

## Decision

Usar Python 3.11.x como version objetivo del proyecto.

## Alternativas consideradas

- Python 3.12 - descartado por mayor riesgo de incompatibilidad con modelos y dependencias de vision.
- Python 3.10 - compatible, pero mas antiguo y menos conveniente como base en 2026.
- Python del sistema - descartado porque acopla el proyecto al estado de Ubuntu y dificulta reproducibilidad.

## Consecuencias

- Positivas: punto medio estable entre soporte moderno y compatibilidad practica.
- Negativas / riesgos: requiere que `uv` gestione una version distinta a la del sistema.

## Notas

Si un blocker real demuestra que Python 3.11 es el problema, se abre un ADR de pivote.

## Aceptación

Aceptada por el usuario el 2026-05-18 vía aprobación verbal en la sesión de planificación (carry-over de Stage 0 documentado en STAGE_1_PROMPT.md).
