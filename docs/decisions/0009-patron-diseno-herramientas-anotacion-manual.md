# ADR-0009: Patrón de diseño para herramientas de anotación manual humana

- **Status:** Aceptada
- **Fecha:** 2026-05-19
- **Stage:** 1

## Contexto

La experiencia del usuario en su proyecto anterior demostró que las herramientas de anotación frame-por-frame estilo "wizard unidireccional" (cada frame se etiqueta y se avanza, sin retroceso) son inviables para humanos cuando los eventos físicos abarcan múltiples frames. En tenis a 60 fps, un bote típicamente ocupa 3-4 frames consecutivos, y un golpe puede ocupar 2-5 frames. El anotador humano no puede saber, viendo solo el frame N, si el evento ocurrió en N, N+1, N+2 o si se trata de un evento que abarca todos esos frames.

## Decisión

Toda herramienta de anotación manual implementada en este proyecto debe cumplir los siguientes requisitos:

a) Navegación bidireccional. El usuario puede avanzar y retroceder frame por frame sin perder el trabajo ya hecho.

b) Salto temporal multi-escala. Botones o atajos para avanzar/retroceder: 1 frame, 10 frames, 1 segundo (~30-60 frames según fps), 10 segundos. Esto permite escanear el rally rápido cuando no pasa nada y bajar a frame-by-frame solo en zonas de interés.

c) Marcado por rango cuando corresponda. Para eventos físicos que duran múltiples frames (botes, golpes, secuencias), la herramienta acepta marcar un frame_range [inicio, fin], no un frame único. El usuario puede definir el inicio en un frame y el fin en otro.

d) Edición y deshacer. Cualquier marca hecha se puede:
- Eliminar antes de cerrar la sesión de anotación.
- Modificar (cambiar el frame_range, cambiar la categoría).
- Re-marcar el mismo frame si pertenece a más de un evento.

e) Vista de contexto. En todo momento el usuario ve:
- El frame actual con su número y timestamp.
- Lista o timeline visual de las marcas ya hechas en la sesión.
- Posición relativa dentro del clip (barra de progreso).

f) Persistencia incremental. La herramienta guarda al disco después de cada marca, no solo al final. Si el browser se cierra, el trabajo no se pierde.

g) Carga de estado existente. Si el usuario reabre la herramienta con anotaciones previas en disco, se cargan y muestran. La sesión es reanudable.

Para herramientas de anotación de POSICIÓN (no eventos, sino x,y de pelota), los requisitos c y g se ajustan a que la unidad de anotación es el clic sobre la imagen, no un rango. Pero el resto aplica igual.

## Alternativas consideradas

- Anotación unidireccional con confirmación al final: descartada, fue el patrón que falló en el proyecto anterior.
- Anotación por intervalos amplios automáticos: descartada, no da control suficiente al anotador humano.

## Consecuencias

- Cada herramienta de anotación va a tomar más tiempo de implementación que un wizard simple. Estimación: +50-100% del tiempo del MVP unidireccional.
- El tiempo de anotación humana por sesión se reduce significativamente y la calidad de la anotación sube. Trade-off claramente favorable.
- El patrón es reusable: una vez implementada bien la primera herramienta (anotación de posición de pelota en Stage 2), las siguientes pueden compartir componentes.

## Notas

ADR aceptado como pre-requisito de iniciar Stage 2.

## Aceptación

Aceptada por el usuario el 2026-05-19 vía aprobación explícita en sesión de planificación.
