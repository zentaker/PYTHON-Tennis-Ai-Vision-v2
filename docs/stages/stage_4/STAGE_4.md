# STAGE 4 - Deteccion y normalizacion de eventos

**Estado:** En progreso - codigo implementado, inputs reales pendientes
**Nivel:** A
**Fecha de preparacion:** 2026-05-19
**Fecha de implementacion base:** 2026-07-13

## Estado operativo Nivel A2

Desde 2026-07-15, Stage 1–3 de `nivel_a2_01` están cerradas y Stage 4 se encuentra en
`ANNOTATOR_IMPLEMENTATION_IN_PROGRESS`. El nuevo anotador local pasó su self-test real
`30/30`: 527 frames exactos, IDs `0–526`, timestamps estrictos y resolución
`2746×1536`. La guía de uso está en
`docs/levels/level_a2/stage_4_annotation_guide.md` y el diseño verificado en
`docs/levels/level_a2/stage_4_annotator_redesign.md`.

La aplicación recibe el video por CLI y oculta todos los inputs técnicos. La página
estática histórica quedó retirada porque no garantizaba navegación frame-accurate.

No existe aún `data/clips/nivel_a2_01/manual_annotation.json`; por ello no se ejecutó el
loader ni se generaron outputs Stage 4. La compatibilidad y el cierre históricos de
Madrid permanecen separados del gate A2.

## Proposito

Convertir `narrative_events` definidos por una persona en eventos internos normalizados
para las etapas de visualizacion posteriores.

Stage 4 Nivel A no detecta botes ni golpes. Valida y transforma solamente los eventos
presentes en `data/reference_clip/manual_annotation.json`; una lista vacia bloquea el
gate y nunca se rellena con suposiciones.

## Estado de implementacion

Implementado:

- schema y vocabularios en `src/events/event_schema.py`;
- loader y export a JSON en `src/events/event_loader.py`;
- overlay de revision en `src/events/render_events_overlay.py`;
- timeline en `src/events/render_events_timeline.py`;
- aplicación local frame-accurate `tools/event_annotator_app/`;
- autosave, restore, undo y export validado;
- self-test real de 30 criterios;
- fixtures sinteticas y tests unitarios sin video real.

Pendiente:

- completar `manual_annotation.json` con conocimiento humano del rally A2;
- ejecutar el pipeline sobre esos datos;
- revisar timeline y overlay;
- obtener el gate humano.

## Inputs

Obligatorios para el gate real:

```text
outputs/stage_3/smoothed_trajectory.csv
data/reference_clip/manual_annotation.json
data/reference_clip/homography.json
```

Auxiliares para anotacion y validacion:

```text
data/reference_clip/madrid_R1.mov
outputs/stage_3/smoothed_trajectory_overlay.mp4
docs/stages/stage_3/exit_report.md
```

La homografia esta versionada. Los demas artefactos reales no existen en el clon actual.
Ver `ASSET_RECOVERY.md`.

## Schema normalizado

Cada evento exportado contiene:

```text
id, type, frame_start, frame_end, frame_mid,
time_start_seconds, time_end_seconds, time_mid_seconds,
player, side, shot_type, court_zone, source, notes
```

Los tiempos se calculan con el FPS indicado por CLI, por el JSON o, si ambos faltan, con
el default de 60 FPS. `frame_range` es inclusivo y debe contener enteros no negativos en
orden. IDs duplicados, eventos fuera de `frames_total` y listas desordenadas se rechazan.

## Flujo operativo A2

1. Iniciar la aplicación con el video canónico ya preparado:

```bash
uv run python -m tools.event_annotator_app \
  --video data/clips/nivel_a2_01/source.mp4 \
  --clip-id nivel_a2_01
```

2. Navegar por imágenes cacheadas, marcar eventos y finalizar la anotación desde la
   interfaz local. No se seleccionan archivos técnicos.
3. Normalizar después de obtener la anotación humana real:

```bash
uv run python -m src.events.event_loader
```

4. Con datos reales validados, generar timeline y overlay:

```bash
uv run python -m src.events.render_events_timeline
uv run python -m src.events.render_events_overlay
```

## Outputs reales esperados

```text
outputs/stage_4/events.json
outputs/stage_4/events_timeline.png
outputs/stage_4/events_overlay.mp4
docs/stages/stage_4/events_report.md
```

Los tres archivos bajo `outputs/` son locales e ignorados por Git. No se generaron en la
implementacion base porque faltan los inputs reales.

## Definition of Done

- Existe un `manual_annotation.json` humano y no vacio.
- El loader convierte todos sus eventos sin perdida ni alteracion semantica.
- Se genera `events.json` con orden y tiempos correctos.
- Timeline y overlay permiten revisar rangos sobre el rally real.
- `events_report.md` registra el run real.
- El usuario confirma que no faltan ni sobran eventos y que los rangos son razonables.

## Gate

Pendiente de validacion humana. Stage 4 no se puede cerrar con fixtures.

El usuario debe confirmar:

- todos los botes narrados estan presentes;
- todos los golpes narrados estan presentes;
- los rangos de frames son razonables;
- no se inventaron eventos;
- no se perdieron eventos durante la normalizacion.

## Fuera de alcance Nivel A

- deteccion automatica de botes o golpes;
- regeneracion de WASB o Stage 3;
- estimacion de altura;
- vista superior o lateral final;
- cualquier trabajo de Stage 5.
