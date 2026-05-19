# ADR-0006: Sistema de coordenadas de cancha y elección de corners

- **Status:** Propuesta
- **Fecha:** 2026-05-18
- **Stage:** 1

## Contexto

Stage 1 necesita una convención única para transformar puntos de píxel del frame de referencia a coordenadas reales sobre el plano de la cancha. La cámara del clip Nivel A muestra líneas de cancha, pero antes de capturar los puntos definitivos el usuario debe confirmar si las líneas de doubles son claramente visibles o si conviene calibrar usando corners de singles.

## Decisión

Usar un sistema de coordenadas en metros con origen en el centro de la red, eje X paralelo a la red y eje Y perpendicular a la red; la elección final de corners exteriores queda parametrizada entre `doubles` y `singles` hasta confirmación del usuario.

## Alternativas consideradas

- Origen en una esquina de la cancha - descartado porque complica la simetría entre lados near/far y la interpretación física posterior.
- Coordenadas normalizadas 0-1 - descartadas porque Stage 5 y Stage 6 necesitan dimensiones reales en metros.
- Fijar doubles sin preguntar - descartado porque algunos clips pueden no mostrar claramente las líneas de doubles y Stage 1 depende de puntos clickeables con baja ambigüedad.

## Consecuencias

- Positivas: las etapas posteriores trabajan en unidades físicas reales y con una convención estable.
- Positivas: el módulo permite elegir `doubles` o `singles` sin reescribir la geometría.
- Negativas / riesgos: la homografía final no debe calcularse hasta que el usuario confirme qué set de corners exteriores se usará.

## Notas

La implementación inicial vive en `src/court/coordinates.py`. Este ADR no se auto-acepta y queda en `Propuesta` hasta aprobación explícita del usuario.
