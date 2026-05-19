# ADR-0001: Uso de WASB como tracker principal

- **Status:** Aceptada
- **Fecha:** 2026-05-18
- **Stage:** 0

## Contexto

El proyecto necesita detectar la pelota de tenis en video real de broadcast. El roadmap prioriza modelos plug-and-play y descarta investigacion aplicada extensa. WASB-SBDT aparece como candidato principal porque esta orientado a tracking de pelota en deportes y permite evaluar rapidamente si el enfoque funciona antes de invertir en fine-tuning o datasets mas grandes.

## Decision

Usar WASB como tracker principal en Stage 2, con fallbacks documentados antes de ejecutar la etapa.

## Alternativas consideradas

- TrackNetV3 - se conserva como Plan B si WASB no alcanza el umbral minimo.
- YOLOv8 fine-tuned - se difiere porque requiere anotacion adicional y posiblemente GPU.
- Baseline clasico HSV/blob - se conserva como Plan D para diagnostico, no como ruta principal.

## Consecuencias

- Positivas: se prueba primero una solucion especifica para pelota y compatible con el principio plug-and-play.
- Negativas / riesgos: puede haber mismatch de dominio con el clip de Madrid; si falla, se pivota sin extender Stage 2 indefinidamente.

## Notas

Stage 0 no instala ni prueba WASB.

## Aceptación

Aceptada por el usuario el 2026-05-18 vía aprobación verbal en la sesión de planificación (carry-over de Stage 0 documentado en STAGE_1_PROMPT.md).
