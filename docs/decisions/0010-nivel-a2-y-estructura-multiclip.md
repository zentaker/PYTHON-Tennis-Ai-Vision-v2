# ADR-0010: Nivel A2 y estructura multi-clip

- **Status:** Aceptada
- **Fecha:** 2026-07-14
- **Stage:** Stage 1, Nivel A2

## Contexto

La pasada historica Madrid R1 cerro Stages 1-3, pero sus artefactos pesados no pudieron
recuperarse en la maquina actual. Un nuevo candidato real permite iniciar otra pasada sin
alterar JSON, documentacion ni conclusiones historicas.

El nuevo archivo tiene extension `.mp4`, codec HEVC, cadence variable y metadata de
rotacion. La estructura anterior dependia en varios defaults del nombre `madrid_R1.mov` y
de una unica carpeta `data/reference_clip/`.

## Decision

- Conservar Madrid R1 como pasada historica Nivel A.
- Denominar la nueva pasada **Nivel A2** y asignar el `clip_id` `nivel_a2_01`.
- Guardar cada fuente canonica bajo `data/clips/<clip_id>/source.<extension>`.
- Conservar la extension original `.mp4` o `.mov`; no renombrar entre formatos.
- Validar metadata ligera mediante `src/project/clip_manifest.py`.
- Separar outputs bajo `outputs/<clip_id>/<stage>/`.
- Exigir que scripts nuevos o modificados reciban rutas explicitas y acepten `.mp4` y
  `.mov`; no hardcodear `madrid_R1`.
- Mantener JSON pequeños por clip (`clip_manifest`, corners, homografia y anotacion) fuera
  de las reglas que ignoran videos y frames derivados.
- No reutilizar homografias, anotaciones o detecciones entre clips.

Para `nivel_a2_01`, el MP4 permanece byte a byte intacto. Los frames derivados de Stage 1
usan una orientacion canonica landscape obtenida con rotacion antihoraria de 90 grados.
Toda futura inferencia debe aplicar exactamente la misma transformacion antes de producir
coordenadas compatibles con la calibracion.

## Alternativas consideradas

- Reutilizar `data/reference_clip/`: descartada porque mezclaria dos pasadas y podria
  sobrescribir evidencia historica.
- Renombrar el MP4 a `.mov`: descartada porque ocultaria el formato de origen sin aportar
  compatibilidad real.
- Reutilizar la homografia Madrid R1: descartada; aunque el torneo y la camara se parezcan,
  cada archivo requiere calibracion propia.
- Corregir/recomprimir el video: descartada; la fuente debe permanecer inmutable.

## Consecuencias

- Positivas: historial preservado, rutas explicitas, outputs aislados y manifests
  verificables.
- Riesgos: algunos scripts historicos conservan defaults Madrid R1 y deberan recibir rutas
  explicitas; la rotacion y la cadence variable de A2 requieren una politica consistente
  antes de Stage 2.
- Stage 2 se prepara con rutas explicitas y contrato canonico; la inferencia sigue
  reservada para Linux/WSL/GPU compatible.

## Aceptacion

Aceptada por instruccion humana el 2026-07-14 al aprobar Stage 1 A2 y solicitar
explicitamente la adaptacion del runner WASB a la arquitectura multi-clip. La
clasificacion B del clip se mantiene por los riesgos de orientacion, HEVC y VFR.
