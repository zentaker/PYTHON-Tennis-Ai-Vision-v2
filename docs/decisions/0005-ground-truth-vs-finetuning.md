# ADR-0005: Anotaciones manuales como ground truth, no training data

- **Status:** Propuesta
- **Fecha:** 2026-05-18
- **Stage:** 0

## Contexto

El usuario aportara anotaciones manuales del clip Nivel A: corners de cancha, eventos narrativos y 20-50 posiciones de pelota. Esas anotaciones pueden tentar a iniciar fine-tuning temprano, pero el roadmap prioriza probar modelos publicados antes de invertir muchas horas de etiquetado.

## Decision

Usar las anotaciones manuales de Stage 0 como ground truth de validacion para Stage 2, no como datos de entrenamiento por defecto.

## Alternativas consideradas

- Fine-tuning inmediato de WASB - descartado porque exige 500-1000 frames adicionales y posiblemente GPU.
- No anotar pelota manualmente - descartado porque impediria medir deteccion con criterio objetivo.
- Anotacion exhaustiva frame-by-frame - descartada porque no es necesaria para el gate inicial.

## Consecuencias

- Positivas: el usuario invierte solo la anotacion minima util para validar.
- Negativas / riesgos: si WASB queda entre 60% y 75%, hara falta decidir si se amplia anotacion.

## Notas

Si WASB detecta al menos 75% sobre ground truth, no se fine-tunea en Stage 2.
