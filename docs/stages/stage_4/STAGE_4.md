# STAGE 4 - Deteccion y normalizacion de eventos

**Estado:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`
**Nivel:** A
**Fecha de preparacion:** 2026-05-19
**Fecha de implementacion base:** 2026-07-13

## Estado operativo Nivel A2

Desde 2026-07-15, Stage 1–3 de `nivel_a2_01` están cerradas y Stage 4 se encuentra en
`IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`. El nuevo anotador local pasó su self-test real
`30/30`: 527 frames exactos, IDs `0–526`, timestamps estrictos y resolución
`2746×1536`. La guía de uso está en
`docs/levels/level_a2/stage_4_annotation_guide.md` y el diseño verificado en
`docs/levels/level_a2/stage_4_annotator_redesign.md`.

La aplicación recibe el video por CLI y oculta todos los inputs técnicos. La página
estática histórica quedó retirada porque no garantizaba navegación frame-accurate.

La anotación humana final de A2 contiene 9 eventos. El loader VFR la normalizó sin
pérdidas y se generaron overlay canónico, timeline y contact sheet. El reporte completo
está en `docs/levels/level_a2/stage_4_execution_report.md`. El cierre histórico de Madrid
permanece compatible y separado del gate A2.

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
- overlay CFR histórico y canónico VFR en `src/events/render_events_overlay.py`;
- timeline VFR en `src/events/render_events_timeline.py`;
- contact sheet en `src/events/render_events_contact_sheet.py`;
- runner reproducible A2 en `src/events/run_stage4_a2.py`;
- aplicación local frame-accurate `tools/event_annotator_app/`;
- autosave, restore, undo y export validado;
- self-test real de 30 criterios;
- fixtures sinteticas y tests unitarios sin video real.

Pendiente:

- revisar overlay, timeline y contact sheet;
- obtener el gate visual humano.

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

Para A2, los tiempos explícitos se verifican contra el índice VFR y nunca se calculan con
FPS nominal. El modo CFR histórico conserva su conversión por FPS para Madrid.
`frame_range` es inclusivo y debe contener enteros no negativos en orden. IDs duplicados,
eventos fuera de `frames_total` y listas desordenadas se rechazan.

## Flujo operativo A2

1. Iniciar la aplicación con el video canónico ya preparado:

```bash
uv run python -m tools.event_annotator_app \
  --video data/clips/nivel_a2_01/source.mp4 \
  --clip-id nivel_a2_01
```

2. Navegar por imágenes cacheadas, marcar eventos y finalizar la anotación desde la
   interfaz local. No se seleccionan archivos técnicos.
3. Normalizar y generar todo el material A2:

```bash
uv run python -m src.events.run_stage4_a2
```

## Outputs reales esperados

```text
outputs/nivel_a2_01/stage_4/events.json
outputs/nivel_a2_01/stage_4/events_timeline.png
outputs/nivel_a2_01/stage_4/events_overlay.mp4
outputs/nivel_a2_01/stage_4/events_contact_sheet.png
outputs/nivel_a2_01/stage_4/events_report.json
```

Los archivos bajo `outputs/` son locales e ignorados por Git. Fueron generados y
validados, pero todavía esperan revisión visual humana.

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
