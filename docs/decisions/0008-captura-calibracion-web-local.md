# ADR-0008: Captura de calibración manual vía servidor HTTP local

- **Status:** Propuesta
- **Fecha:** 2026-05-19
- **Stage:** 1

## Contexto

El fallback manual inicial para Stage 1 pedía al usuario reportar coordenadas numéricas de píxel desde una herramienta como Paint o IrfanView. Ese flujo fue descartado porque el usuario no tiene ni debe tener una herramienta de medición digital. La calibración debe seguir siendo manual, pero mediante clics directos sobre el frame de referencia.

## Decisión

Implementar la captura manual de los 8 puntos de calibración mediante un servidor HTTP local en `http://localhost:8765`, usando `http.server` de la biblioteca estándar y una página web con JavaScript para capturar clics.

## Alternativas consideradas

- Pedir coordenadas numéricas al usuario - descartado por mala usabilidad y riesgo alto de errores.
- Instalar Flask - descartado porque `http.server` alcanza para un servidor local de una sola pantalla.
- Resolver WSLg/Qt antes de continuar - descartado para Stage 1 porque el navegador de Windows ofrece una ruta más simple y suficiente.

## Consecuencias

- Positivas: el usuario calibra por clic, no por transcripción manual de píxeles.
- Positivas: no se agregan dependencias nuevas al entorno.
- Positivas: el servidor puede ejecutar sanity checks antes de persistir el JSON.
- Negativas / riesgos: requiere abrir una URL local en el navegador y mantener vivo el proceso hasta completar los 8 clics.

## Notas

El servidor escribe `data/reference_clip/court_corners_pixel.json` con método `manual_web_click` y se cierra automáticamente después de una captura exitosa. Este ADR queda en `Propuesta` hasta aprobación explícita del usuario.
