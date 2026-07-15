# Guía de anotación humana — Stage 4 A2

**Estado:** `WAITING_FOR_MANUAL_ANNOTATION`
**Clip:** `nivel_a2_01`
**Frames requeridos:** `527` (`0–526`)

## Objetivo y límites

Registrar manualmente los eventos visibles del rally. La herramienta no detecta ni
inventa eventos. En esta fase no se normaliza el JSON, no se genera timeline u overlay
y no se inicia Stage 5.

No crear un archivo vacío ni copiar eventos de otro clip. La ruta canónica final es:

`data/clips/nivel_a2_01/manual_annotation.json`

## Archivos que debe seleccionar el usuario

- Video: `data/clips/nivel_a2_01/source.mp4`.
- Sidecar temporal VFR: `data/clips/nivel_a2_01/frame_timestamps.json`.
- Herramienta: `tools/manual_event_annotator/index.html`.

La herramienta valida que el sidecar pertenezca a `nivel_a2_01`, declare VFR, contenga
exactamente 527 frames, tenga IDs consecutivos y timestamps estrictamente crecientes.

## Eventos

1. `serve`: contacto inicial de la raqueta con la pelota durante el saque.
2. `bounce`: cada bote visible de la pelota dentro o fuera de la cancha.
3. `hit`: cada contacto posterior de la raqueta de un jugador con la pelota.
4. `unknown`: usar solo cuando se observa un evento pero su tipo no puede determinarse.

La herramienta permite exclusivamente `serve`, `hit`, `bounce` y `unknown`. No agregar
eventos inferidos de la trayectoria ni anotar movimiento sin un evento visible.

## Player

- `near`: jugador más cercano a la cámara.
- `far`: jugador más lejano.
- `unknown`: solo cuando no sea posible determinarlo.

## Frame range

- Para un contacto o bote puntual, usar normalmente un solo frame.
- Para un solo frame, usar **Usar frame actual** tanto en Frame inicio como en Frame
  fin.
- Si el momento es ambiguo entre varios frames, usar un rango corto.
- No usar rangos largos que abarquen movimiento sin evento.
- Los frames válidos son `0–526`; inicio y fin son inclusivos.

Los segundos se calculan desde los timestamps VFR reales del frame inicial y final, no
desde un FPS constante.

## Shot type

- Usar el tipo de golpe cuando sea claramente visible.
- Usar `unknown` cuando exista duda.
- No adivinar.

Opciones disponibles: `saque`, `derecha`, `revés`, `derecha_invertida`,
`revés_invertido`, `slice`, `volea`, `dejada`, `globo`, `unknown`.

## Court zone

- Usar una zona solamente cuando pueda determinarse visualmente.
- Usar `unknown` cuando exista duda.

Opciones disponibles: `zona_saque_derecha`, `zona_saque_izquierda`, `fondo`, `media`,
`aprox_red`, `red`, `unknown`.

## Orden mínimo orientativo del rally

Ejemplo:

```text
serve
bounce
hit
bounce
hit
bounce
hit
```

No asumir que todos los rallies siguen exactamente ese patrón. Registrar únicamente lo
que sea visible y mantener los eventos en orden cronológico.

## Operación paso a paso

1. Abrir `tools/manual_event_annotator/index.html`.
2. En **Archivo de video**, cargar `source.mp4`.
3. En **Sidecar temporal VFR**, cargar `frame_timestamps.json`.
4. Confirmar que aparezca `Sidecar VFR válido: 527 frames`.
5. Reproducir o pausar el video y avanzar con las flechas frame por frame.
6. Pausar en cada evento visible.
7. Para un evento puntual, pulsar **Usar frame actual** en inicio y fin; para una
   ambigüedad breve, marcar los dos extremos del rango.
8. Completar tipo, player y únicamente los datos conocidos. Usar `unknown` ante duda.
9. Pulsar **Guardar evento**.
10. Revisar la tabla y su orden cronológico; editar o eliminar errores desde la propia
    herramienta.
11. Pulsar **Exportar manual_annotation.json**.
12. Colocar el archivo exportado en
    `data/clips/nivel_a2_01/manual_annotation.json`.
13. No editar manualmente el JSON salvo que sea necesario; si se edita, conservar
    frames, tiempos VFR, vocabularios y orden.

La herramienta se niega a exportar si no existen eventos humanos, si falta el video o
si no se cargó el sidecar VFR.

## Auditoría de preparación A2

| Requisito | Resultado |
| --- | --- |
| Carga `source.mp4` local | OK |
| Carga `frame_timestamps.json` | OK |
| Usa timestamps VFR reales | OK |
| Navegación frame a frame | OK |
| Exige 527 frames para A2 | OK |
| Exporta `frame_start` y `frame_end` | OK |
| Exporta `time_start_seconds` y `time_end_seconds` | OK |
| Vocabulario de eventos/player restringido | OK |
| Impide exportar lista vacía | OK |
| Nombre exportado `manual_annotation.json` | OK |

No fue necesario modificar código. El loader conserva compatibilidad histórica con
Madrid y acepta los tiempos VFR explícitos exportados por el anotador A2.

## Outputs futuros, todavía no generados

Después de recibir y validar la anotación humana se podrán generar:

```text
outputs/nivel_a2_01/stage_4/events.json
outputs/nivel_a2_01/stage_4/events_timeline.png
outputs/nivel_a2_01/stage_4/events_overlay.mp4
outputs/nivel_a2_01/stage_4/events_report.json
```

No ejecutar todavía la normalización ni los renderizadores. Stage 4 debe detenerse en
`WAITING_FOR_MANUAL_ANNOTATION` hasta que el usuario entregue el JSON real.
