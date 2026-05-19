# Exit Report - Stage 2

**Estado:** Cerrada exitosa con limitaciones conocidas  
**Fecha de cierre:** 2026-05-19  
**Nivel:** A

## Resumen

Stage 2 produjo detecciones de pelota por frame usando WASB-SBDT con pesos preentrenados de tenis. El resultado principal fue un CSV local con coordenadas por frame y un MP4 local con detecciones sobreimpresas para validacion visual humana.

El usuario reviso `outputs/stage_2/wasb_detections_overlay.mp4` y emitio veredicto humano positivo: WASB es visualmente aceptable para continuar a Stage 3.

## Artefactos principales

- `data/reference_clip/wasb_detections.csv`
- `outputs/stage_2/wasb_detections_overlay.mp4`
- `src/tracker/wasb_runner.py`
- `docs/stages/stage_2/local_continuity_audit.md`

Nota: el CSV, el MP4, el checkpoint y `third_party/` son artefactos locales ignorados por `.gitignore` por diseno. No deben commitearse.

## Metricas tecnicas

- Frames totales: `949`
- Frames procesados: `949`
- Frames con `confidence >= 0.5`: `804`
- Detection rate aparente: `84.72%`
- Confidence minima: `0.038088`
- Confidence maxima: `0.955775`
- Confidence media: `0.746542`
- Confidence mediana: `0.859709`
- Resolucion del overlay: `1920x1080`
- FPS del overlay: `60`
- Duracion del overlay: `15.816667 s`

## Advertencia metodologica

Detection rate aparente no equivale a ground truth formal.

Las metricas anteriores indican que WASB produjo detecciones con confianza sobre el clip completo, pero no sustituyen la validacion visual humana ni una medicion formal contra puntos anotados manualmente.

## Veredicto humano

WASB es visualmente aceptable para continuar a Stage 3.

## Limitacion observada

Se observaron 4 errores/desvios puntuales, principalmente en momentos de impacto del jugador far/lejos de la camara. En esos frames, el marcador puede separarse de la pelota real o perder trazabilidad local.

## Impacto de la limitacion

La limitacion no bloquea el proyecto porque los errores parecen aislados y Stage 3 esta disenado para suavizar trayectoria, rechazar outliers e interpolar gaps cortos.

## Decision

No pivotar de modelo. No hacer fine-tuning. Continuar a Stage 3.

## Deuda

Si Stage 3 no logra absorber estos errores, se reabrira Stage 2 para revision de thresholds, frames clave o preprocesado.

## Estado final

Stage 2 queda cerrado como viable para Nivel A, con limitaciones visuales conocidas. No se avanza a Stage 3 en este cierre; solo se deja preparado el handoff documental.
