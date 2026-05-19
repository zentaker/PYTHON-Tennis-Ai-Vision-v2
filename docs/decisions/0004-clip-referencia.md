# ADR-0004: Madrid Open R1 como clip de referencia

- **Status:** Propuesta
- **Fecha:** 2026-05-18
- **Stage:** 0

## Contexto

Para evitar validar contra impresiones subjetivas, el proyecto necesita un clip Nivel A unico y estable. Ese clip debe permitir anotacion manual razonable, tener camara fija y representar una escena real de broadcast. El roadmap define Madrid Open rally R1 como sandbox supervisado.

## Decision

Usar `data/reference_clip/madrid_R1.mp4` como clip de referencia Nivel A.

## Alternativas consideradas

- Otro rally del mismo torneo - se reserva para Nivel B, donde se prueba generalizacion dentro de escena.
- Hamburg Open - se reserva para Nivel C, donde cambia la escena.
- Clips sinteticos - descartados porque no validan la friccion real de broadcast.

## Consecuencias

- Positivas: unifica todos los criterios de Stage 1 a Stage 7 en Nivel A.
- Negativas / riesgos: si el clip no esta disponible o no tiene camara fija, se debe abrir ADR de reemplazo.

## Notas

El video real no se commitea. Debe existir localmente para cerrar Stage 0.
