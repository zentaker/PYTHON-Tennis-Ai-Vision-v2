# STAGE 4 - Deteccion y normalizacion de eventos

**Estado:** En progreso - codigo implementado, inputs reales pendientes
**Nivel:** A
**Fecha de preparacion:** 2026-05-19
**Fecha de implementacion base:** 2026-07-13

## Estado operativo Nivel A2

Desde 2026-07-15, Stage 1–3 de `nivel_a2_01` están cerradas y la preparación A2 se
encuentra en `WAITING_FOR_MANUAL_ANNOTATION`. El video y el sidecar VFR están disponibles
localmente; ya no aplica a A2 la recuperación de assets descrita para el entorno
histórico Madrid.

El anotador fue auditado para `527` frames, navegación mediante timestamps VFR y export
de frames/tiempos explícitos. Guía específica:
`docs/levels/level_a2/stage_4_annotation_guide.md`.

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
- herramienta estatica `tools/manual_event_annotator/index.html`;
- fixtures sinteticas y tests unitarios sin video real.

Pendiente:

- recuperar el clip y la trayectoria suavizada de la maquina anterior;
- crear/completar `manual_annotation.json` con conocimiento humano del rally;
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

## Flujo operativo

1. Abrir `tools/manual_event_annotator/index.html` en un navegador.
2. Cargar el video local y confirmar FPS.
3. Registrar, revisar, editar y ordenar los eventos humanos.
4. Exportar `manual_annotation.json` y colocarlo en `data/reference_clip/`.
5. Normalizar:

```bash
uv run python -m src.events.event_loader
```

6. Con datos reales validados, generar timeline y overlay:

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
