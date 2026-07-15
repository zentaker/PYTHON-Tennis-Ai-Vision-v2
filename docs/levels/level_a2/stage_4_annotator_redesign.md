# Rediseño del anotador de Stage 4 — Nivel A2

**Estado:** `IMPLEMENTED_PENDING_HUMAN_VISUAL_GATE`

**Fecha:** 2026-07-15

**Self-test local:** `PASSED_30_30`

## Decisión

El anotador estático anterior fue rechazado y quedó retirado. Dependía del seeking
aproximado del navegador, exponía archivos técnicos y no garantizaba que cada paso
mostrara el frame lógico solicitado. La herramienta activa es ahora una aplicación
local con backend Python y una interfaz servida exclusivamente en `127.0.0.1`.

Se inicia con el video canónico ya definido por CLI:

```bash
uv run python -m tools.event_annotator_app \
  --video data/clips/nivel_a2_01/source.mp4 \
  --clip-id nivel_a2_01
```

La persona que anota no selecciona el video ni carga manifest, timestamps, FPS,
rutas, hashes u otros archivos técnicos. La URL local se muestra y se abre con el
comando estándar de macOS.

## Índice exacto y caché

El backend valida internamente los metadatos temporales disponibles o los obtiene con
FFprobe, y decodifica secuencialmente con
`src.video.canonical_frames.iter_canonical_frames`. El ID proviene exclusivamente de
la posición del decoder, nunca de `timestamp × FPS` ni del reproductor del navegador.

La sesión A2 verificada contiene:

- 527 frames con IDs consecutivos `0–526`;
- timestamps estrictamente crecientes;
- resolución horizontal canónica `2746×1536`;
- duración aproximada de 10.488334 segundos;
- una imagen WebP y una entrada de índice por frame.

La caché ignorada por Git vive en:

```text
.cache/event_annotator/<video_sha256>/
├── frame_index.json
└── frames/frame_000000.webp ... frame_000526.webp
```

Un ID repetido, ausente o fuera de orden es un error crítico. En cambio, dos frames
pueden tener el mismo contenido visual: conservan imágenes, IDs y timestamps separados,
y se marcan como `duplicate_visual_content=true`; nunca se fusionan.

## Navegación y visor

El frontend solicita directamente `/api/frames/{frame_id}`. No contiene un elemento
`video` ni usa seeking. El contador, imagen, timestamp, duración y tira de miniaturas se
actualizan para un mismo ID; una carga pendiente bloquea una segunda navegación. Se
precargan los frames cercanos y la reproducción avanza con la duración real de cada
entrada.

Las verificaciones obligatorias confirmaron:

- `0→1→2→1`;
- `10→11→12→13→12→11→10`;
- 100 pasos adelante y 100 atrás sin deriva;
- rutas independientes para `frame_000011.webp`, `frame_000012.webp` y
  `frame_000013.webp`;
- rechazo estricto de `-1` y `527`.

## Impactos y ayudas visuales

Un evento sin selección usa el frame actual. Para un impacto multiframe se marca inicio
y fin, se navega sin perder el rango y luego se pulsa el tipo de evento. El backend
deriva nuevamente los timestamps del índice. La prueba integrada creó correctamente el
rango `132–134`, con tiempos reales `2.638333–2.671667 s` y duración de tres frames.

La interfaz ofrece zoom, comparación anterior/actual/siguiente y, cuando existe la
trayectoria Stage 3, un toggle de pelota trackeada y recortes alrededor de ella. La
aplicación conserva toda su funcionalidad si el tracking opcional no está disponible.

## Eventos, persistencia y exportación

Los presets crean saque, golpe, bote o evento desconocido sin inferir zona ni subtipo de
golpe. La tabla cronológica permite editar detalles o eliminar. Los IDs son automáticos;
los rangos se validan contra `0–526`, y los tiempos no son editables.

Cada cambio se guarda atómicamente en el borrador local ignorado por Git. La sesión se
restaura al reiniciar y ofrece deshacer. La exportación final solo se habilita con al
menos un evento y vuelve a comprobar hashes de inputs, conteo, orden, bounds,
timestamps, esquema y aceptación por `src.events.event_loader`. La ruta de salida es
fija; el usuario no la selecciona.

## API local

La aplicación expone:

- `GET /api/session`, `/api/self-test`, `/api/events`;
- `GET /api/frames/{id}` y `/api/frames/{id}/metadata`;
- `POST /api/events`, `/api/events/undo`, `/api/export`;
- `PATCH /api/events/{id}`;
- `DELETE /api/events/{id}`.

Las imágenes se leen de la caché; ningún request busca dentro del video.

## Self-test y prueba end-to-end

Antes de habilitar la anotación se ejecutan 30 criterios: presencia e integridad de
inputs, timestamps, decodificación, IDs, resolución, legibilidad de extremos, rutas,
navegación, bounds, eventos puntuales y multiframe, autosave, undo, restore, export,
compatibilidad del loader e inmutabilidad de los inputs. El resultado real fue
`PASSED_30_30`.

Una prueba HTTP aislada recorrió frames `0,1,2,1,100,101`, creó el evento `132–134`, lo
deshizo, reinició y restauró un borrador de fixture, lo eliminó y confirmó el estado
limpio. No creó anotaciones ni borradores de prueba en las rutas reales.

## Criterios de presentación

La herramienta solo se presenta si:

- el video ya está preparado y no hay selectores técnicos;
- `FRAME 000 / 526` avanza exactamente a 001, 002 y vuelve a 001;
- cada ID entrega su imagen cacheada y las miniaturas conservan IDs distintos;
- los impactos multiframe pueden marcarse sin escribir números;
- guardar, editar, eliminar, autosave, restore y undo funcionan;
- la interfaz no requiere conocimiento técnico;
- self-test, suite completa y arranque local terminan correctamente.

## Plan B

El fallback no fue activado porque los criterios críticos pasaron. Si una verificación
crítica fallara antes de la prueba humana, no se entregaría una versión parcial: Stage 4
pasaría a una hoja simple producida en un editor de video con tiempo inicial, tiempo
final, evento, jugador, lado y notas. El sistema convertiría esos tiempos a frames con
el índice interno.

La anotación humana real fue completada y procesada posteriormente; ver
`stage_4_execution_report.md`. Stage 4 sigue abierta hasta el gate visual de los outputs.
Stage 5 no ha comenzado.
